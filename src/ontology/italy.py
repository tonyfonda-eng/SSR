import re

__version__ = "1.0"

DICTIONARY = {
    r"\bacquisizione\b": "ACQUISITION",
    r"\bofferta pubblica\b": "TENDER_OFFER",
    r"\bfusione\b": "MERGER",
    
    # Event Status
    r"\bvoce\b": "RUMOUR",
    r"\bpossibile\b": "POSSIBLE",
    r"\bnon vincolante\b": "NON_BINDING",
    r"\baccordo definitivo\b": "DEFINITIVE_AGREEMENT",
    r"\bcompletato\b": "COMPLETED",
    r"\bterminato\b": "TERMINATED"
}

def normalize(text):
    text_lower = text.lower()
    terms = set()
    for pattern, concept in DICTIONARY.items():
        if re.search(pattern, text_lower):
            terms.add(concept)
    return list(terms)
