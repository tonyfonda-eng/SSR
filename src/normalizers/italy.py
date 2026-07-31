import re

DICTIONARY = {
    r"\bacquisizione\b": "CANONICAL_ACQUISITION",
    r"\bofferta pubblica\b": "CANONICAL_TENDER_OFFER",
    r"\bfusione\b": "CANONICAL_MERGER"
}

def normalize(text):
    text_lower = text.lower()
    terms = set()
    for pattern, concept in DICTIONARY.items():
        if re.search(pattern, text_lower):
            terms.add(concept)
    return list(terms)
