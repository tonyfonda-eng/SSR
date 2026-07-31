import re

DICTIONARY = {
    # Dutch
    r"\bovername\b": "CANONICAL_ACQUISITION",
    r"\bfusie\b": "CANONICAL_MERGER",
    r"\bopenbaar bod\b": "CANONICAL_TENDER_OFFER",
    
    # Swedish
    r"\buppköpserbjudande\b": "CANONICAL_TENDER_OFFER",
    r"\bförvärv\b": "CANONICAL_ACQUISITION",
    r"\bfusion\b": "CANONICAL_MERGER",
    
    # Norwegian
    r"\boppkjøp\b": "CANONICAL_ACQUISITION",
    r"\btilbud\b": "CANONICAL_TENDER_OFFER"
}

def normalize(text):
    text_lower = text.lower()
    terms = set()
    for pattern, concept in DICTIONARY.items():
        if re.search(pattern, text_lower):
            terms.add(concept)
    return list(terms)
