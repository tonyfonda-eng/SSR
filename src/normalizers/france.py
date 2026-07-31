import re

DICTIONARY = {
    r"\boffre publique d'achat\b": "CANONICAL_TENDER_OFFER",
    r"\boffre publique\b": "CANONICAL_TENDER_OFFER",
    r"\boffre d'achat\b": "CANONICAL_CASH_OFFER",
    r"\bfusion\b": "CANONICAL_MERGER",
    r"\bacquisition\b": "CANONICAL_ACQUISITION"
}

def normalize(text):
    text_lower = text.lower()
    terms = set()
    for pattern, concept in DICTIONARY.items():
        if re.search(pattern, text_lower):
            terms.add(concept)
    return list(terms)
