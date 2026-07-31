import re
import string

def normalize_issuer(name):
    """
    Normalizes an issuing company name to improve deterministic deduplication.
    - Uppercase
    - Removes punctuation
    - Strips common corporate suffixes (INC, CORP, PLC, etc.)
    """
    if not name or name.strip().upper() == "UNKNOWN":
        return "UNKNOWN"
        
    # 1. Uppercase and strip whitespace
    name = name.strip().upper()
    
    # 2. Remove punctuation
    name = name.translate(str.maketrans('', '', string.punctuation))
    
    # 3. Strip common corporate suffixes repeatedly
    # Using \b to ensure we match whole words at the end of the string
    suffixes = [
        "INC", "CORPORATION", "CORP", "PLC", "LIMITED", "LTD", 
        "SA", "NV", "AG", "HOLDINGS", "HOLDING", "LLC", "LP", "COMPANY", "CO"
    ]
    
    # Regex: match a space, then any suffix, at the end of the string.
    # Optional trailing spaces handled by strip().
    suffix_pattern = r'\b(?:' + '|'.join(suffixes) + r')\b$'
    
    while True:
        # Strip to ensure $ matches the actual end of the text
        name = name.strip()
        new_name = re.sub(suffix_pattern, '', name).strip()
        if new_name == name:
            break
        name = new_name
        
    # If the name gets stripped to nothing (e.g. they literally named the company "Inc"), revert
    return name if name else "UNKNOWN"

def extract_issuing_company(source_name, title, body):
    """
    Extracts the issuing company from the article using deterministic methods first,
    falling back to AI if necessary.
    """
    # 1. SEC EDGAR extraction
    if source_name == "SEC EDGAR":
        # Usually title is formatted as "8-K [1.01] - Louisiana-Pacific Corp"
        if " - " in title:
            issuer = title.split(" - ")[-1].strip()
            return normalize_issuer(issuer)
            
    # 2. Extract from standard PR Dateline (PR Newswire / GlobeNewswire / BusinessWire)
    # Dateline typically looks like: "NEW YORK, July 31, 2026 /PRNewswire/ -- Stryker Corporation today announced..."
    # Or "TORONTO, July 31 (GlobeNewswire) -- DeepHealth..."
    
    # Since extracting accurately across 3 providers and 1000s of formats using Regex is extremely fragile,
    # and we don't have access to the raw HTML metadata in this scope,
    # we rely on the cheap AI fallback which is remarkably good at this specific task.
    
    # 3. Fallback to AI
    from src.ai import _call_llm_pool
    
    prompt = f"""
Return ONLY the company issuing this announcement.
If you cannot determine it, return UNKNOWN.
Do not return a ticker, return the formal company name.
Article Title: {title}
Article Body: {body[:1500]}
"""
    
    try:
        response = _call_llm_pool(prompt)
        issuer = response.strip()
        if not issuer or issuer == "UNKNOWN":
            return "UNKNOWN"
            
        # Very long responses usually indicate hallucination or the AI returning the whole sentence.
        if len(issuer) > 50:
            return "UNKNOWN"
            
        return normalize_issuer(issuer)
    except Exception as e:
        print(f"    [AI ERROR] Issuer Extraction failed: {e}")
        return "UNKNOWN"
