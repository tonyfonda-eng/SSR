import re

DICTIONARY = {
    r"\bübernahme\b": "CANONICAL_ACQUISITION",
    r"\bbarangebot\b": "CANONICAL_CASH_OFFER",
    r"\bfusion\b": "CANONICAL_MERGER",
    r"\babspaltung\b": "CANONICAL_SPINOFF",
    r"\bsonderdividende\b": "CANONICAL_SPECIAL_DIVIDEND",
    r"\bdelisting\b": "CANONICAL_DELISTING",
    r"\binsolvenz\b": "CANONICAL_BANKRUPTCY"
}

def normalize(text):
    text_lower = text.lower()
    terms = set()
    for pattern, concept in DICTIONARY.items():
        if re.search(pattern, text_lower):
            terms.add(concept)
    return list(terms)
