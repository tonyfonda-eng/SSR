import re

DICTIONARY = {
    r"\badquisición\b": "CANONICAL_ACQUISITION",
    r"\bfusión\b": "CANONICAL_MERGER",
    r"\boferta pública de adquisición\b": "CANONICAL_TENDER_OFFER",
    r"\bopa\b": "CANONICAL_TENDER_OFFER"
}

def normalize(text):
    text_lower = text.lower()
    terms = set()
    for pattern, concept in DICTIONARY.items():
        if re.search(pattern, text_lower):
            terms.add(concept)
    return list(terms)
