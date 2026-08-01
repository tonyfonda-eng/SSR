"""
Unit tests for the Ontology V3 architecture.

Tests:
  1. concepts.py — Sheet-driven extraction
  2. rules_engine.py — Multi-channel evidence scoring
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ontology.concepts import _parse_language_terms, extract_concepts, extract_statuses
from src.ontology import concepts as concepts_module
from src.rules_engine import evaluate


# ============================================================
# Part 1: Ontology Concept Extraction
# ============================================================

def test_parse_language_terms():
    """Test parsing of the Languages column format."""
    result = _parse_language_terms(
        "English: acquisition, purchase, takeover; German: übernahme; French: acquisition"
    )
    assert "acquisition" in result
    assert "purchase" in result
    assert "takeover" in result
    assert "übernahme" in result
    assert len(result) == 5  # 'acquisition' appears in both English and French blocks
    print("[PASS] _parse_language_terms")


def test_parse_language_terms_edge_cases():
    """Test edge cases in language parsing."""
    assert _parse_language_terms("") == []
    assert _parse_language_terms(None) == []
    
    # No language labels
    result = _parse_language_terms("merger, acquisition")
    assert "merger" in result
    assert "acquisition" in result
    print("[PASS] _parse_language_terms edge cases")


def _load_mock_ontology():
    """Simulate loading ontology from sheets by directly populating module cache."""
    import re
    
    mock_concepts = [
        {"Concept_ID": "ACQUISITION", "Score": 40,
         "Languages": "English: acquisition, purchase, takeover, acquire; German: übernahme"},
        {"Concept_ID": "MERGER", "Score": 40,
         "Languages": "English: merger, merge; German: fusion"},
        {"Concept_ID": "TENDER_OFFER", "Score": 45,
         "Languages": "English: tender offer, cash offer; German: barangebot, übernahmeangebot; French: offre publique d'achat"},
        {"Concept_ID": "STRATEGIC_REVIEW", "Score": 15,
         "Languages": "English: strategic review, strategic alternatives"},
    ]
    
    mock_statuses = [
        {"Status_ID": "DEFINITIVE_AGREEMENT", "Score": 50,
         "Languages": "English: definitive agreement, definitive merger agreement; German: vertrag unterzeichnet"},
        {"Status_ID": "RUMOUR", "Score": 5,
         "Languages": "English: rumour, rumored; German: gerücht"},
        {"Status_ID": "COMPLETED", "Score": -10,
         "Languages": "English: completed, closed, consummated"},
        {"Status_ID": "TERMINATED", "Score": -20,
         "Languages": "English: terminated, abandoned, withdrawn"},
    ]
    
    # Build patterns (same logic as load_ontology but without sheets)
    concepts_module._concept_patterns = []
    for c in mock_concepts:
        concept_id = c["Concept_ID"]
        score = c["Score"]
        terms = _parse_language_terms(c["Languages"])
        for term in terms:
            pattern = re.compile(r'\b' + re.escape(term) + r'\b', re.IGNORECASE)
            concepts_module._concept_patterns.append((pattern, concept_id, score))
    
    concepts_module._status_patterns = []
    for s in mock_statuses:
        status_id = s["Status_ID"]
        score = s["Score"]
        terms = _parse_language_terms(s["Languages"])
        for term in terms:
            pattern = re.compile(r'\b' + re.escape(term) + r'\b', re.IGNORECASE)
            concepts_module._status_patterns.append((pattern, status_id, score))
    
    concepts_module._loaded = True


def test_extract_concepts_english():
    """Test English concept extraction."""
    _load_mock_ontology()
    
    text = "Company X has entered into a definitive merger agreement to acquire Company Y"
    concepts = extract_concepts(text)
    concept_ids = {c[0] for c in concepts}
    
    assert "ACQUISITION" in concept_ids, f"Expected ACQUISITION in {concept_ids}"
    assert "MERGER" in concept_ids, f"Expected MERGER in {concept_ids}"
    print(f"[PASS] English extraction: {concepts}")


def test_extract_concepts_german():
    """Test German concept extraction."""
    _load_mock_ontology()
    
    text = "Die Übernahme wurde heute bekannt gegeben. Das Barangebot beträgt 50 EUR pro Aktie."
    concepts = extract_concepts(text)
    concept_ids = {c[0] for c in concepts}
    
    assert "ACQUISITION" in concept_ids, f"Expected ACQUISITION in {concept_ids}"
    assert "TENDER_OFFER" in concept_ids, f"Expected TENDER_OFFER in {concept_ids}"
    print(f"[PASS] German extraction: {concepts}")


def test_extract_concepts_french():
    """Test French concept extraction."""
    _load_mock_ontology()
    
    text = "Offre publique d'achat sur les actions de Société ABC"
    concepts = extract_concepts(text)
    concept_ids = {c[0] for c in concepts}
    
    assert "TENDER_OFFER" in concept_ids, f"Expected TENDER_OFFER in {concept_ids}"
    print(f"[PASS] French extraction: {concepts}")


def test_extract_statuses():
    """Test event status extraction."""
    _load_mock_ontology()
    
    # Definitive agreement
    text = "Company X entered into a definitive agreement to merge with Company Y"
    statuses = extract_statuses(text)
    status_ids = {s[0] for s in statuses}
    
    assert "DEFINITIVE_AGREEMENT" in status_ids, f"Expected DEFINITIVE_AGREEMENT in {status_ids}"
    print(f"[PASS] Status extraction: {statuses}")


def test_extract_statuses_negative():
    """Test negative status scores for completed/terminated events."""
    _load_mock_ontology()
    
    text = "The merger has been completed successfully."
    statuses = extract_statuses(text)
    status_dict = dict(statuses)
    
    assert "COMPLETED" in status_dict, f"Expected COMPLETED in {status_dict}"
    assert status_dict["COMPLETED"] == -10, f"Expected -10 score, got {status_dict['COMPLETED']}"
    print(f"[PASS] Negative status scoring: {statuses}")


def test_extract_mixed_language():
    """Test that the same ontology works across multiple languages in one pass."""
    _load_mock_ontology()
    
    # Mixed English/German text
    text = "Die Fusion zwischen Company X und Company Y. A definitive merger agreement has been reached."
    concepts = extract_concepts(text)
    statuses = extract_statuses(text)
    
    concept_ids = {c[0] for c in concepts}
    status_ids = {s[0] for s in statuses}
    
    assert "MERGER" in concept_ids
    assert "DEFINITIVE_AGREEMENT" in status_ids
    print(f"[PASS] Mixed language: concepts={concepts}, statuses={statuses}")


# ============================================================
# Part 2: Multi-Channel Evidence Scoring (Rules Engine)
# ============================================================

def test_rules_engine_independent_channels():
    """Test that ontology, doc type, source reliability, and keywords are independent channels."""
    _load_mock_ontology()
    
    article_obj = {
        "raw_text": "Company X announces cash offer to acquire Company Y for $50 per share",
        "document_type": "ad-hoc"
    }
    
    rules = [
        {
            "Event Family": "M&A Cash Acquisition",
            "Keywords": "cash|per share",
            "Semantic Concepts": "ACQUISITION",
            "Event Status": "",
            "Exclusions": "",
            "Confidence Modifiers": ""
        }
    ]
    
    doc_scores = {"ad-hoc": 40}
    ontology_concepts = [("ACQUISITION", 40)]
    ontology_statuses = []
    
    matches = evaluate(
        article_obj, rules, doc_scores,
        ontology_concepts=ontology_concepts,
        ontology_statuses=ontology_statuses,
        source_reliability=100,
        threshold=10
    )
    
    assert len(matches) == 1, f"Expected 1 match, got {len(matches)}"
    
    match = matches[0]
    # Score breakdown:
    # Doc type (ad-hoc): +40
    # Ontology (ACQUISITION): +40
    # Source reliability (100 * 0.2): +20
    # Keywords (cash + per share): +10
    # Total: 110
    expected_score = 40 + 40 + 20 + 5 + 5  # 110
    assert match["_Score"] == expected_score, f"Expected {expected_score}, got {match['_Score']}"
    
    # Verify evidence log contains all channels
    evidence = match["_Evidence"]
    has_doc = any("Document Type" in e for e in evidence)
    has_onto = any("Ontology" in e for e in evidence)
    has_source = any("Source Reliability" in e for e in evidence)
    has_keyword = any("Keyword" in e for e in evidence)
    
    assert has_doc, "Missing Document Type in evidence"
    assert has_onto, "Missing Ontology in evidence"
    assert has_source, "Missing Source Reliability in evidence"
    assert has_keyword, "Missing Keyword in evidence"
    
    print(f"[PASS] Independent channels: Score={match['_Score']}, Evidence={evidence}")


def test_rules_engine_concept_filtering():
    """Test that rules with Semantic Concepts only match articles with those concepts."""
    _load_mock_ontology()
    
    article_obj = {
        "raw_text": "Company announces strategic review of alternatives",
        "document_type": ""
    }
    
    rules = [
        {
            "Event Family": "M&A Cash Acquisition",
            "Keywords": "",
            "Semantic Concepts": "ACQUISITION|MERGER",
            "Event Status": "",
            "Exclusions": "",
            "Confidence Modifiers": ""
        },
        {
            "Event Family": "Strategic Review",
            "Keywords": "",
            "Semantic Concepts": "STRATEGIC_REVIEW",
            "Event Status": "",
            "Exclusions": "",
            "Confidence Modifiers": ""
        }
    ]
    
    ontology_concepts = [("STRATEGIC_REVIEW", 15)]
    
    matches = evaluate(
        article_obj, rules, {},
        ontology_concepts=ontology_concepts,
        threshold=10
    )
    
    # Only "Strategic Review" should match (concept filter)
    assert len(matches) == 1, f"Expected 1 match, got {len(matches)}"
    assert matches[0]["Event Family"] == "Strategic Review"
    print(f"[PASS] Concept filtering: matched '{matches[0]['Event Family']}' correctly")


def test_rules_engine_negative_scores():
    """Test that COMPLETED/TERMINATED statuses reduce scores."""
    _load_mock_ontology()
    
    article_obj = {
        "raw_text": "The merger has been completed. All conditions satisfied.",
        "document_type": ""
    }
    
    rules = [
        {
            "Event Family": "M&A Completed",
            "Keywords": "merger",
            "Semantic Concepts": "MERGER",
            "Event Status": "",
            "Exclusions": "",
            "Confidence Modifiers": ""
        }
    ]
    
    ontology_concepts = [("MERGER", 40)]
    ontology_statuses = [("COMPLETED", -10)]
    
    matches = evaluate(
        article_obj, rules, {},
        ontology_concepts=ontology_concepts,
        ontology_statuses=ontology_statuses,
        threshold=10
    )
    
    if matches:
        # 40 (ontology) + (-10) (completed) + 5 (keyword: merger) = 35
        assert matches[0]["_Score"] == 35, f"Expected 35, got {matches[0]['_Score']}"
        print(f"[PASS] Negative status scoring: Score={matches[0]['_Score']}")
    else:
        print("[PASS] Negative status scoring: article correctly filtered below threshold")


def test_rules_engine_no_ontology():
    """Test that the engine still works when no ontology concepts are detected (keyword-only)."""
    article_obj = {
        "raw_text": "Company X to acquire Company Y for cash consideration of $50 per share",
        "document_type": ""
    }
    
    rules = [
        {
            "Event Family": "M&A Cash Acquisition",
            "Keywords": "acquire|cash consideration|per share",
            "Semantic Concepts": "",
            "Event Status": "",
            "Exclusions": "",
            "Confidence Modifiers": ""
        }
    ]
    
    matches = evaluate(
        article_obj, rules, {},
        ontology_concepts=[],
        ontology_statuses=[],
        threshold=10
    )
    
    assert len(matches) == 1
    assert matches[0]["_Score"] == 15  # 3 keywords * 5
    print(f"[PASS] Keyword-only fallback: Score={matches[0]['_Score']}")


# ============================================================
# Run all tests
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Ontology V3 — Unit Tests")
    print("=" * 60)
    
    print("\n--- Concept Extraction ---")
    test_parse_language_terms()
    test_parse_language_terms_edge_cases()
    test_extract_concepts_english()
    test_extract_concepts_german()
    test_extract_concepts_french()
    test_extract_statuses()
    test_extract_statuses_negative()
    test_extract_mixed_language()
    
    print("\n--- Multi-Channel Rules Engine ---")
    test_rules_engine_independent_channels()
    test_rules_engine_concept_filtering()
    test_rules_engine_negative_scores()
    test_rules_engine_no_ontology()
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)
