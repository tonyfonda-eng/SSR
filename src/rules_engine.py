"""
Investment playbook engine based on Multi-Channel Evidence Scoring.

Each article accumulates evidence independently from several channels:
  1. Document Type      — from Google Sheets
  2. Ontology Concept   — from Google Sheets (language-agnostic)
  3. Event Status       — from Google Sheets (deal stage)
  4. Source Reliability — from Google Sheets
  5. Keywords           — rule-specific regex matching
  6. Confidence Modifiers — rule-specific custom points

Python executes. Google Sheets decides.
"""
import re


def evaluate(article_obj, rules, document_type_scores,
             ontology_concepts=None, ontology_statuses=None,
             source_reliability=0, threshold=15):
    """
    Evaluates a structured article against multi-channel evidence scoring.

    Parameters:
        article_obj: dict with 'raw_text', 'document_type'
        rules: list of rule dicts from Google Sheets
        document_type_scores: dict or list mapping doc type -> int score
        ontology_concepts: list of (concept_id, score) tuples from extract_concepts()
        ontology_statuses: list of (status_id, score) tuples from extract_statuses()
        source_reliability: int reliability score for this article's source (0-100)
        threshold: minimum total score to qualify

    Returns a list of candidate rules that met or exceeded the threshold.
    """
    if ontology_concepts is None:
        ontology_concepts = []
    if ontology_statuses is None:
        ontology_statuses = []

    # ---- Defensive Normalization for document_type_scores ----
    scores_map = {}
    if isinstance(document_type_scores, dict):
        scores_map = {str(k).lower().strip(): v for k, v in document_type_scores.items()}
    elif isinstance(document_type_scores, list):
        for item in document_type_scores:
            if isinstance(item, dict):
                dt = item.get('Document Type') or item.get('document_type') or item.get('type')
                sc = item.get('Score') or item.get('score', 0)
                if dt:
                    try:
                        scores_map[str(dt).lower().strip()] = float(sc) if '.' in str(sc) else int(sc)
                    except (ValueError, TypeError):
                        scores_map[str(dt).lower().strip()] = 0

    matches = []

    text = str(article_obj.get("raw_text", "")).lower()
    doc_type = str(article_obj.get("document_type", "")).lower().strip()

    # ---- Independent Evidence Channels (apply to ALL rules) ----

    # Channel 1: Document Type (Safely using scores_map lookup)
    doc_score = scores_map.get(doc_type, 0)

    # Channel 2: Ontology Concepts (independent, sheet-defined weights)
    ontology_score = sum(score for _, score in ontology_concepts)
    concept_ids = {cid for cid, _ in ontology_concepts}

    # Channel 3: Event Status (independent, sheet-defined weights)
    status_score = sum(score for _, score in ontology_statuses)
    status_ids = {sid for sid, _ in ontology_statuses}

    # Channel 4: Source Reliability (normalised to a 0-20 contribution)
    source_score = int(source_reliability * 0.2) if source_reliability else 0

    # Base score that every rule starts with (from independent channels)
    base_score = doc_score + ontology_score + status_score + source_score

    for rule in rules:
        score = base_score
        evidence_log = []

        # Log independent channels
        if doc_score != 0:
            evidence_log.append(f"Document Type: {doc_type} ({doc_score:+d})")
        for cid, cscore in ontology_concepts:
            evidence_log.append(f"Ontology: {cid} ({cscore:+d})")
        for sid, sscore in ontology_statuses:
            evidence_log.append(f"Event Status: {sid} ({sscore:+d})")
        if source_score > 0:
            evidence_log.append(f"Source Reliability: {source_reliability} ({source_score:+d})")

        # ---- Rule-Specific Filtering ----
        semantic_raw = str(rule.get("Semantic Concepts", "")).strip().upper()
        if semantic_raw:
            rule_concepts = {x.strip() for x in re.split(r'[,|]', semantic_raw) if x.strip()}
            if not rule_concepts & concept_ids:
                continue

        status_raw = str(rule.get("Event Status", "")).strip().upper()
        if status_raw:
            rule_statuses = {x.strip() for x in re.split(r'[,|]', status_raw) if x.strip()}
            if not rule_statuses & status_ids:
                continue

        exclusions_raw = str(rule.get("Exclusions", "")).strip()
        if exclusions_raw:
            exclusions = [x.strip().lower() for x in re.split(r'[,|]', exclusions_raw) if x.strip()]
            if any(re.search(r'\b' + re.escape(exc) + r'\b', text) for exc in exclusions):
                continue

        keywords_raw = str(rule.get("Keywords", "")).strip()
        if keywords_raw:
            keywords = [x.strip().lower() for x in re.split(r'[,|]', keywords_raw) if x.strip()]
            for kw in keywords:
                if re.search(r'\b' + re.escape(kw) + r'\b', text):
                    score += 5
                    evidence_log.append(f"Keyword: {kw} (+5)")

        modifiers_raw = str(rule.get("Confidence Modifiers", "")).strip()
        if modifiers_raw:
            mods = [x.strip().lower() for x in re.split(r'[,|]', modifiers_raw) if x.strip()]
            for mod in mods:
                match = re.match(r"^(.+?)\s*\+(\d+)$", mod)
                if match:
                    phrase = match.group(1).strip()
                    points = int(match.group(2))
                    if phrase and re.search(r'\b' + re.escape(phrase) + r'\b', text):
                        score += points
                        evidence_log.append(f"Modifier: {phrase} (+{points})")

        if score >= threshold:
            candidate = dict(rule)
            candidate["_Score"] = score
            candidate["_Evidence"] = evidence_log
            matches.append(candidate)

    matches.sort(key=lambda x: x["_Score"], reverse=True)
    return matches
