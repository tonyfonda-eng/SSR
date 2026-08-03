"""
Investment playbook engine based on Multi-Channel Evidence Scoring.
"""
import re

def evaluate(article_obj, rules, document_type_scores,
             ontology_concepts=None, ontology_statuses=None,
             source_reliability=0, threshold=15):
    
    if ontology_concepts is None:
        ontology_concepts = []
    if ontology_statuses is None:
        ontology_statuses = []

    # Strict type casting for incoming thresholds
    try:
        threshold = float(threshold)
    except (ValueError, TypeError):
        threshold = 15.0

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

    # Channel 1: Document Type
    doc_score = scores_map.get(doc_type, 0)
    ontology_score = sum(score for _, score in ontology_concepts)
    concept_ids = {cid for cid, _ in ontology_concepts}
    status_score = sum(score for _, score in ontology_statuses)
    status_ids = {sid for sid, _ in ontology_statuses}

    # Safe casting for source reliability
    try:
        safe_source_rel = float(source_reliability)
        source_score = int(safe_source_rel * 0.2)
    except (ValueError, TypeError):
        source_score = 0

    base_score = doc_score + ontology_score + status_score + source_score

    for rule in rules:
        score = base_score
        evidence_log = []

        if doc_score != 0:
            evidence_log.append(f"Document Type: {doc_type} ({doc_score:+d})")
        for cid, cscore in ontology_concepts:
            evidence_log.append(f"Ontology: {cid} ({cscore:+d})")
        for sid, sscore in ontology_statuses:
            evidence_log.append(f"Event Status: {sid} ({sscore:+d})")
        if source_score > 0:
            evidence_log.append(f"Source Reliability: {safe_source_rel} ({source_score:+d})")

        # Filtering: Semantic Concepts
        semantic_raw = str(rule.get("Semantic Concepts", "")).strip().upper()
        if semantic_raw:
            rule_concepts = {x.strip() for x in re.split(r'[,|]', semantic_raw) if x.strip()}
            if not rule_concepts & concept_ids:
                continue

        # Filtering: Event Status
        status_raw = str(rule.get("Event Status", "")).strip().upper()
        if status_raw:
            rule_statuses = {x.strip() for x in re.split(r'[,|]', status_raw) if x.strip()}
            if not rule_statuses & status_ids:
                continue

        # Filtering: Exclusions
        exclusions_raw = str(rule.get("Exclusions", "")).strip()
        if exclusions_raw:
            exclusions = [re.escape(x.strip().lower()) for x in re.split(r'[,|]', exclusions_raw) if x.strip()]
            if exclusions:
                # Compile one single regex for ALL exclusions to save CPU
                exc_pattern = re.compile(r'\b(' + '|'.join(exclusions) + r')\b')
                if exc_pattern.search(text):
                    continue

        # Keywords Scoring
        keywords_raw = str(rule.get("Keywords", "")).strip()
        if keywords_raw:
            keywords = [x.strip().lower() for x in re.split(r'[,|]', keywords_raw) if x.strip()]
            for kw in keywords:
                # Fast string matching before falling back to Regex boundaries
                if kw in text and re.search(r'\b' + re.escape(kw) + r'\b', text):
                    score += 5
                    evidence_log.append(f"Keyword: {kw} (+5)")

        # Modifiers Scoring (Now supports positive AND negative points)
        modifiers_raw = str(rule.get("Confidence Modifiers", "")).strip()
        if modifiers_raw:
            mods = [x.strip().lower() for x in re.split(r'[,|]', modifiers_raw) if x.strip()]
            for mod in mods:
                # Regex allows '+' or '-' (e.g. "rumor -10" or "definitive agreement +20")
                match = re.match(r"^(.+?)\s*([+-]?\d+)$", mod)
                if match:
                    phrase = match.group(1).strip()
                    points = int(match.group(2))
                    if phrase and phrase in text and re.search(r'\b' + re.escape(phrase) + r'\b', text):
                        score += points
                        evidence_log.append(f"Modifier: {phrase} ({points:+d})")

        # Final Threshold Check
        if score >= threshold:
            candidate = dict(rule)
            # CRITICAL FIX: Removed underscores to align with monitor.py expectations
            candidate["Score"] = score
            candidate["Evidence"] = evidence_log
            matches.append(candidate)

    matches.sort(key=lambda x: x.get("Score", 0), reverse=True)
    return matches