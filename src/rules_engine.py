"""
SSR 2.0: Deterministic Rules Engine (Layer B)
Executes versioned rule packs against immutable text payloads.
Extracts strict causal chains via character offset mapping and records 
both supporting (matched) and opposing (failed) evidentiary nodes.
"""

import re
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

def evaluate(article: dict, rules: list, document_type_scores: list,
             ontology_concepts: list = None, ontology_statuses: list = None,
             source_reliability: int = 0, threshold: int = 10) -> List[Dict[str, Any]]:
    """
    Executes the deterministic rule matrix.
    
    Returns a list of matching rule nodes. The first element contains the aggregate
    score and the full Causal Evidence Graph (including Opposing Evidence) to maintain
    compatibility with the orchestrator payload expectations.
    """
    raw_text = article.get("raw_text", "")
    doc_type = article.get("document_type", "Unknown")
    
    total_score = float(source_reliability)
    supporting_evidence = []
    opposing_evidence = []
    matches = []
    
    # ---------------------------------------------------------
    # 1. Document Type Baseline Scoring
    # ---------------------------------------------------------
    doc_score = 0.0
    for dt in document_type_scores:
        if dt.get("Document Type") == doc_type:
            doc_score = float(dt.get("Score", 0))
            break
            
    total_score += doc_score
    if doc_score > 0:
        supporting_evidence.append({
            "component": "DocType Validator v1.0",
            "assertion": f"Target document format matched: '{doc_type}'",
            "weight": doc_score,
            "causal_link": None
        })
    elif doc_type and doc_type != "Unknown":
        opposing_evidence.append({
            "component": "DocType Validator v1.0",
            "assertion": f"Document format '{doc_type}' lacks positive score mapping",
            "weight": 0.0,
            "causal_link": None
        })

    # ---------------------------------------------------------
    # 2. Ontology Baseline Scoring
    # ---------------------------------------------------------
    ont_score = 0.0
    if ontology_concepts:
        for concept, weight in ontology_concepts:
            ont_score += float(weight)
            supporting_evidence.append({
                "component": "Ontology Core Taxonomy",
                "assertion": f"Semantic concept extracted: {concept}",
                "weight": float(weight),
                "causal_link": None
            })
    else:
        opposing_evidence.append({
            "component": "Ontology Core Taxonomy",
            "assertion": "No baseline semantic concepts detected",
            "weight": 1.0,
            "causal_link": None
        })
        
    total_score += ont_score

    # ---------------------------------------------------------
    # 3. Deterministic Causal Rule Matrix
    # ---------------------------------------------------------
    for rule in rules:
        rule_id = rule.get("Rule ID", "UNKNOWN")
        # Lineage Tracking: Defaults to v1.0 if not present in the Google Sheet yet
        rule_version = rule.get("Version", "v1.0") 
        component_tag = f"Rule {rule_id} {rule_version}"
        
        target_pattern = rule.get("Regex Pattern", "")
        base_score = float(rule.get("Score", 0))
        is_exclusion = str(rule.get("Exclusion", "")).strip().upper() == "TRUE"
        
        if not target_pattern:
            continue
            
        try:
            # Execute Regex with absolute character offset tracking (Causal Links)
            regex_matches = list(re.finditer(target_pattern, raw_text, re.IGNORECASE))
            
            if regex_matches:
                first_match = regex_matches[0]
                match_text = first_match.group(0)
                
                # The causal link maps the decision precisely to the text coordinate
                causal_link = {
                    "text_start_offset": first_match.start(),
                    "text_end_offset": first_match.end()
                }
                
                if is_exclusion:
                    # Deterministic Hard Drop via Exclusion Pattern
                    opposing_evidence.append({
                        "component": component_tag,
                        "assertion": f"Terminal Exclusion triggered on string: '{match_text}'",
                        "weight": 1.0,
                        "causal_link": causal_link
                    })
                    logger.info(f"[RULES ENGINE] Hard exclusion triggered by {rule_id}")
                    return [] # Instant exit; scores are voided
                else:
                    total_score += base_score
                    supporting_evidence.append({
                        "component": component_tag,
                        "assertion": f"Positive pattern evaluation on string: '{match_text}'",
                        "weight": base_score,
                        "causal_link": causal_link
                    })
                    matches.append({
                        "Rule": rule_id,
                        "Summary": rule.get("Description", f"Pattern matched: {target_pattern}"),
                        "Score": base_score,
                        "MatchText": match_text,
                        "Offsets": causal_link
                    })
            else:
                # Capture explicitly negative evidence (rules that did NOT fire)
                if not is_exclusion:
                    opposing_evidence.append({
                        "component": component_tag,
                        "assertion": f"Required pattern signature missing: '{target_pattern}'",
                        "weight": 0.0,
                        "causal_link": None
                    })
                
        except re.error as e:
            logger.error(f"[RULES ENGINE] Invalid regex compilation in {rule_id}: {e}")
            continue

    # ---------------------------------------------------------
    # 4. Institutional Threshold Validation
    # ---------------------------------------------------------
    if total_score >= threshold:
        # Pack the aggregate score and full evidentiary DAG into the first match
        # to preserve backward compatibility with the monitor.py signature interface.
        if not matches:
            # Edge case: Ontology/DocType passed the threshold, but no regex rule fired
            matches.append({
                "Rule": "AGGREGATE_BASELINE",
                "Summary": "Institutional threshold satisfied entirely via Ontology/DocType baselines.",
                "Score": total_score,
                "MatchText": "",
                "Offsets": None
            })
        
        # Hydrate the return payload with the new SSR 2.0 Canonical Structure variables
        matches[0]["Score"] = total_score
        matches[0]["Evidence"] = supporting_evidence
        matches[0]["Opposing_Evidence"] = opposing_evidence
        return matches
        
    # Score fell below threshold; returns empty list acting as a silent deterministic drop
    return []