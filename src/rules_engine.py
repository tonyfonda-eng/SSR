"""
Investment playbook engine based on Evidence Scoring.
"""
import re

def evaluate(article_text, rules, threshold=15):
    """
    Evaluates an article against the point-based Evidence Scoring rules.
    Returns a list of candidate rules that met or exceeded the threshold, sorted by score.
    """
    matches = []
    text = article_text.lower()

    for rule in rules:
        score = 0
        
        # 1. Check Exclusions (instant disqualification)
        exclusions_raw = str(rule.get("Exclusions", "")).strip()
        if exclusions_raw:
            exclusions = [x.strip().lower() for x in re.split(r'[,|]', exclusions_raw) if x.strip()]
            if any(exc in text for exc in exclusions):
                # An exclusion was hit, disqualify this rule
                continue

        # 2. Accumulate base points from Keywords
        keywords_raw = str(rule.get("Keywords", "")).strip()
        evidence_log = []
        if keywords_raw:
            keywords = [x.strip().lower() for x in re.split(r'[,|]', keywords_raw) if x.strip()]
            for kw in keywords:
                if kw in text:
                    score += 5  # Base points for a keyword
                    evidence_log.append(f"Keyword: {kw} (+5)")

        # 3. Accumulate points from Confidence Modifiers
        # e.g., "all cash +10, board approved +5"
        modifiers_raw = str(rule.get("Confidence Modifiers", "")).strip()
        if modifiers_raw:
            # Split by comma or pipe
            mods = [x.strip().lower() for x in re.split(r'[,|]', modifiers_raw) if x.strip()]
            for mod in mods:
                # Regex to extract phrase and points: e.g. "all cash +10" -> "all cash", "10"
                match = re.match(r"^(.*?)\s*\+?(\d+)$", mod)
                if match:
                    phrase = match.group(1).strip()
                    points = int(match.group(2))
                    if phrase and phrase in text:
                        score += points
                        evidence_log.append(f"Modifier: {phrase} (+{points})")

        # 4. Check if threshold met
        if score >= threshold:
            candidate = dict(rule)
            candidate["_Score"] = score
            candidate["_Evidence"] = evidence_log
            matches.append(candidate)

    # Sort matches by score descending
    matches.sort(key=lambda x: x["_Score"], reverse=True)
    return matches
