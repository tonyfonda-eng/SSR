import re

__version__ = "1.0"

DICTIONARY = {
    r"\bübernahme\b": "ACQUISITION",
    r"\bbarangebot\b": "CASH_OFFER",
    r"\bfusion\b": "MERGER",
    r"\babspaltung\b": "SPINOFF",
    r"\bsonderdividende\b": "SPECIAL_DIVIDEND",
    r"\bdelisting\b": "DELISTING",
    r"\binsolvenz\b": "LIQUIDATION",
    
    # Event Status
    r"\bgerücht\b": "RUMOUR",
    r"\bmöglich\b": "POSSIBLE",
    r"\bunverbindlich\b": "NON_BINDING",
    r"\bvertrag unterzeichnet\b": "DEFINITIVE_AGREEMENT",
    r"\babgeschlossen\b": "COMPLETED",
    r"\bbeendet\b": "TERMINATED"
}

def normalize(text):
    text_lower = text.lower()
    terms = set()
    for pattern, concept in DICTIONARY.items():
        if re.search(pattern, text_lower):
            terms.add(concept)
    return list(terms)
