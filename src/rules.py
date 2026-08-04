"""
SSR 2.0: Rules Helper Module
Exposes global and issuer exclusion matching functions for the orchestrator.
"""
import re
import logging

logger = logging.getLogger(__name__)

def matches_global_exclusion(body_text: str, global_exclusions: list = None) -> bool:
    """
    Checks if the body text contains any blacklisted global exclusion keywords or regex patterns.
    """
    if not body_text:
        return False
        
    default_exclusions = ["Form 4", "Schedule 13G", "Statement of Changes in Ownership"]
    exclusions = [e.get("Keyword", e.get("Pattern", "")) for e in (global_exclusions or []) if e.get("Keyword", e.get("Pattern"))]
    if not exclusions:
        exclusions = default_exclusions

    text_lower = body_text.lower()
    for exc in exclusions:
        if not exc:
            continue
        try:
            if re.search(r'\b' + re.escape(exc.lower()) + r'\b', text_lower):
                return True
        except re.error:
            if exc.lower() in text_lower:
                return True
                
    return False

def matches_issuer_exclusion(source_name: str, sources_config: list = None) -> bool:
    """
    Checks if a given sensor source is blacklisted or inactive based on configuration.
    """
    if not source_name or not sources_config:
        return False
        
    for src in sources_config:
        name = src.get("Source Name", src.get("Source", ""))
        active = str(src.get("Active", "TRUE")).upper()
        if name.lower() == source_name.lower() and active != "TRUE":
            return True
            
    return False
