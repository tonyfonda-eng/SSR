import re

__version__ = "1.0"

DICTIONARY = {
    r"\boffre publique d'achat\b": "TENDER_OFFER",
    r"\boffre publique\b": "TENDER_OFFER",
    r"\boffre d'achat\b": "CASH_OFFER",
    r"\bfusion\b": "MERGER",
    r"\bacquisition\b": "ACQUISITION",
    
    # Event Status
    r"\brumeur\b": "RUMOUR",
    r"\bpossible\b": "POSSIBLE",
    r"\bnon contraignant\b": "NON_BINDING",
    r"\baccord définitif\b": "DEFINITIVE_AGREEMENT",
    r"\bterminé\b": "COMPLETED",
    r"\bannulé\b": "TERMINATED"
}

def normalize(text):
    text_lower = text.lower()
    terms = set()
    for pattern, concept in DICTIONARY.items():
        if re.search(pattern, text_lower):
            terms.add(concept)
    return list(terms)
