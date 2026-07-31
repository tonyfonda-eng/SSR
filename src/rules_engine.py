"""
Investment playbook engine based on Evidence Scoring.
"""
import re

def evaluate(article_obj, rules, document_type_scores, threshold=15):
    """
    Evaluates a structured article against the point-based Evidence Scoring rules.
    article_obj should contain: raw_text, normalized_terms (list), document_type
    Returns a list of candidate rules that met or exceeded the threshold.
    """
    matches = []
    
    text = str(article_obj.get("raw_text", "")).lower()
    normalized_terms = [t.strip().upper() for t in article_obj.get("normalized_terms", [])]
    doc_type = str(article_obj.get("document_type", "")).lower().strip()
    
    # 1. Document Type Channel
    doc_score = document_type_scores.get(doc_type, 0)
    
    for rule in rules:
        score = doc_score
        evidence_log = []
        
        if doc_score > 0:
            evidence_log.append(f"Document Type: {doc_type} (+{doc_score})")
            
        # 2. Check Exclusions (instant disqualification)
        exclusions_raw = str(rule.get("Exclusions", "")).strip()
        if exclusions_raw:
            exclusions = [x.strip().lower() for x in re.split(r'[,|]', exclusions_raw) if x.strip()]
            if any(re.search(r'\b' + re.escape(exc) + r'\b', text) for exc in exclusions):
                continue

        # 3. Ontology Channel (Semantic Concepts)
        semantic_raw = str(rule.get("Semantic Concepts", "")).strip().upper()
        if semantic_raw:
            semantic_concepts = [x.strip() for x in re.split(r'[,|]', semantic_raw) if x.strip()]
            for concept in semantic_concepts:
                if concept in normalized_terms:
                    score += 10 # Base score for semantic match
                    evidence_log.append(f"Ontology Concept: {concept} (+10)")
                    
        # 4. Ontology Channel (Event Status)
        status_raw = str(rule.get("Event Status", "")).strip().upper()
        if status_raw:
            statuses = [x.strip() for x in re.split(r'[,|]', status_raw) if x.strip()]
            for status in statuses:
                if status in normalized_terms:
                    score += 5
                    evidence_log.append(f"Event Status: {status} (+5)")

        # 5. Keyword Channel
        keywords_raw = str(rule.get("Keywords", "")).strip()
        if keywords_raw:
            keywords = [x.strip().lower() for x in re.split(r'[,|]', keywords_raw) if x.strip()]
            for kw in keywords:
                if re.search(r'\b' + re.escape(kw) + r'\b', text):
                    score += 5
                    evidence_log.append(f"Keyword: {kw} (+5)")

        # 6. Confidence Modifiers Channel
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

        # Check if threshold met
        if score >= threshold:
            candidate = dict(rule)
            candidate["_Score"] = score
            candidate["_Evidence"] = evidence_log
            matches.append(candidate)

    matches.sort(key=lambda x: x["_Score"], reverse=True)
    return matches
