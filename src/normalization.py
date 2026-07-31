import re

# Dictionary mapping foreign regulatory/M&A terms to the canonical English terms 
# used in the Google Sheets "Rules" tab. 
# Key: Regex pattern for foreign word. Value: Canonical English equivalent.
DICTIONARY = {
    # German
    r"\bübernahme\b": "acquisition",
    r"\bbarangebot\b": "cash offer",
    r"\bfusion\b": "merger",
    r"\babspaltung\b": "spin-off",
    r"\bsonderdividende\b": "special dividend",
    r"\bdelisting\b": "delisting",
    r"\binsolvenz\b": "bankruptcy",
    
    # French
    r"\boffre publique d'achat\b": "tender offer",
    r"\boffre publique\b": "tender offer",
    r"\boffre d'achat\b": "cash offer",
    r"\bfusion\b": "merger",
    r"\bacquisition\b": "acquisition",
    
    # Italian
    r"\bacquisizione\b": "acquisition",
    r"\bofferta pubblica\b": "tender offer",
    r"\bfusione\b": "merger",
    
    # Spanish
    r"\badquisición\b": "acquisition",
    r"\bfusión\b": "merger",
    r"\boferta pública de adquisición\b": "tender offer",
    r"\bopa\b": "tender offer",
    
    # Dutch
    r"\bovername\b": "acquisition",
    r"\bfusie\b": "merger",
    r"\bopenbaar bod\b": "tender offer",
    
    # Swedish
    r"\buppköpserbjudande\b": "tender offer",
    r"\bförvärv\b": "acquisition",
    r"\bfusion\b": "merger",
    
    # Norwegian
    r"\boppkjøp\b": "acquisition",
    r"\btilbud\b": "tender offer"
}

def normalize_text(text):
    """
    Scans the native article text for foreign keywords and appends the canonical 
    English equivalents to the bottom of the string.
    This lightweight string is then fed to the Rules Engine (which evaluates English regex).
    """
    text_lower = text.lower()
    added_terms = set()
    
    for pattern, english_term in DICTIONARY.items():
        if re.search(pattern, text_lower):
            added_terms.add(english_term)
            
    if added_terms:
        # Append the canonical English terms purely for the rules engine's regex evaluation
        # The original text remains intact for Gemini.
        return text + "\n\n--- NORMALIZED KEYWORDS ---\n" + "\n".join(added_terms)
        
    return text
