"""
Investment playbook engine based on Evidence Scoring.
"""
import re

DOCUMENT_TYPE_SCORES = {
    "ad-hoc": 40,
    "inside information": 40,
    "información privilegiada": 40,
    "price sensitive": 35,
    "regulated information": 30,
    "regulatory": 30,
    "corporate news": 5,
    "press release": 0
}

def evaluate(article_obj, rules, threshold=15):
    """
    Evaluates a structured article against the point-based Evidence Scoring rules.
    article_obj should contain: raw_text, normalized_terms (list), document_type
    Returns a list of candidate rules that met or exceeded the threshold.
    """
    matches = []
    
    text = str(article_obj.get("raw_text", "")).lower()
    normalized_terms = [t.lower() for t in article_obj.get("normalized_terms", [])]
    doc_type = str(article_obj.get("document_type", "")).lower()
    
    # Pre-calculate document type score
    doc_score = DOCUMENT_TYPE_SCORES.get(doc_type, 0)
    
    for rule in rules:
        score = doc_score
        evidence_log = []
        
        if doc_score > 0:
            evidence_log.append(f"Document Type: {doc_type} (+{doc_score})")
            
        # 1. Check Exclusions (instant disqualification)
        exclusions_raw = str(rule.get("Exclusions", "")).strip()
        if exclusions_raw:
            exclusions = [x.strip().lower() for x in re.split(r'[,|]', exclusions_raw) if x.strip()]
            if any(re.search(r'\b' + re.escape(exc) + r'\b', text) for exc in exclusions) or any(exc in normalized_terms for exc in exclusions):
                continue

        # 2. Accumulate base points from Keywords
        keywords_raw = str(rule.get("Keywords", "")).strip()
        if keywords_raw:
            keywords = [x.strip().lower() for x in re.split(r'[,|]', keywords_raw) if x.strip()]
            for kw in keywords:
                # Check both raw text and normalized semantic concepts
                if kw in normalized_terms or re.search(r'\b' + re.escape(kw) + r'\b', text):
                    score += 5  # Base points for a keyword
                    evidence_log.append(f"Keyword/Concept: {kw} (+5)")

        # 3. Accumulate points from Confidence Modifiers
        modifiers_raw = str(rule.get("Confidence Modifiers", "")).strip()
        if modifiers_raw:
            mods = [x.strip().lower() for x in re.split(r'[,|]', modifiers_raw) if x.strip()]
            for mod in mods:
                match = re.match(r"^(.+?)\s*\+(\d+)$", mod)
                if match:
                    phrase = match.group(1).strip()
                    points = int(match.group(2))
                    if phrase and (phrase in normalized_terms or re.search(r'\b' + re.escape(phrase) + r'\b', text)):
                        score += points
                        evidence_log.append(f"Modifier: {phrase} (+{points})")

        # 4. Check if threshold met
        if score >= threshold:
            candidate = dict(rule)
            candidate["_Score"] = score
            candidate["_Evidence"] = evidence_log
            matches.append(candidate)

    matches.sort(key=lambda x: x["_Score"], reverse=True)
    return matches
