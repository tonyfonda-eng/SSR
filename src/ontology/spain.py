import re

__version__ = "1.0"

DICTIONARY = {
    r"\badquisición\b": "ACQUISITION",
    r"\bfusión\b": "MERGER",
    r"\boferta pública de adquisición\b": "TENDER_OFFER",
    r"\bopa\b": "TENDER_OFFER",
    
    # Event Status
    r"\brumor\b": "RUMOUR",
    r"\bposible\b": "POSSIBLE",
    r"\bno vinculante\b": "NON_BINDING",
    r"\bacuerdo definitivo\b": "DEFINITIVE_AGREEMENT",
    r"\bcompletado\b": "COMPLETED",
    r"\bterminado\b": "TERMINATED"
}

def normalize(text):
    text_lower = text.lower()
    terms = set()
    for pattern, concept in DICTIONARY.items():
        if re.search(pattern, text_lower):
            terms.add(concept)
    return list(terms)
