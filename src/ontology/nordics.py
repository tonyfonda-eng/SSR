import re

__version__ = "1.0"

DICTIONARY = {
    # Dutch
    r"\bovername\b": "ACQUISITION",
    r"\bfusie\b": "MERGER",
    r"\bopenbaar bod\b": "TENDER_OFFER",
    
    # Swedish
    r"\buppköpserbjudande\b": "TENDER_OFFER",
    r"\bförvärv\b": "ACQUISITION",
    r"\bfusion\b": "MERGER",
    
    # Norwegian
    r"\boppkjøp\b": "ACQUISITION",
    r"\btilbud\b": "TENDER_OFFER",
    
    # Event Status
    r"\brykte\b": "RUMOUR",
    r"\bgerucht\b": "RUMOUR",
    r"\bmöjlig\b": "POSSIBLE",
    r"\bmogelijk\b": "POSSIBLE",
    r"\bbindande avtal\b": "DEFINITIVE_AGREEMENT",
    r"\bdefinitieve overeenkomst\b": "DEFINITIVE_AGREEMENT"
}

def normalize(text):
    text_lower = text.lower()
    terms = set()
    for pattern, concept in DICTIONARY.items():
        if re.search(pattern, text_lower):
            terms.add(concept)
    return list(terms)
