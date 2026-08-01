"""
Corporate Action Ontology — Sheet-Driven Concept Extraction.

Loads semantic concepts and event statuses from Google Sheets,
builds a unified regex dictionary covering all languages,
and extracts matching concepts from article text.

This replaces the per-country hardcoded dictionaries (germany.py, france.py, etc.)
with a single, language-agnostic extraction engine driven by the Google Workbook.
"""
import re

# Module-level cache: populated once at startup by load_ontology()
_concept_patterns = []   # [(compiled_regex, concept_id, score), ...]
_status_patterns = []    # [(compiled_regex, status_id, score), ...]
_loaded = False


def _parse_language_terms(languages_str):
    """
    Parses the Languages column from Google Sheets into a list of regex patterns.
    
    Expected format:
        "English: acquisition, purchase, takeover; German: übernahme; French: acquisition"
    
    Returns a list of raw term strings (lowercased) to be compiled as word-boundary regex.
    """
    terms = []
    if not languages_str:
        return terms
    
    # Split by semicolons to get language blocks
    blocks = languages_str.split(";")
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        
        # Split on first colon to separate language label from terms
        if ":" in block:
            _, term_part = block.split(":", 1)
        else:
            term_part = block
        
        # Split terms by commas
        for term in term_part.split(","):
            term = term.strip().lower()
            if term:
                terms.append(term)
    
    return terms


def load_ontology(sheet_url):
    """
    Loads semantic concepts and event statuses from Google Sheets.
    Builds compiled regex patterns for fast extraction.
    
    Called once at pipeline startup.
    """
    global _concept_patterns, _status_patterns, _loaded
    
    from src.sheets import load_semantic_concepts, load_event_statuses
    
    # --- Load Semantic Concepts ---
    concepts = load_semantic_concepts(sheet_url)
    _concept_patterns = []
    
    for concept in concepts:
        concept_id = str(concept.get("Concept_ID", "")).strip().upper()
        if not concept_id:
            continue
        
        try:
            score = int(concept.get("Score", 0))
        except (ValueError, TypeError):
            score = 0
        
        languages_str = str(concept.get("Languages", ""))
        terms = _parse_language_terms(languages_str)
        
        for term in terms:
            try:
                pattern = re.compile(r'\b' + re.escape(term) + r'\b', re.IGNORECASE)
                _concept_patterns.append((pattern, concept_id, score))
            except re.error:
                print(f"[ONTOLOGY WARNING] Invalid regex for term '{term}' in concept {concept_id}")
    
    # --- Load Event Statuses ---
    statuses = load_event_statuses(sheet_url)
    _status_patterns = []
    
    for status in statuses:
        status_id = str(status.get("Status_ID", "")).strip().upper()
        if not status_id:
            continue
        
        try:
            score = int(status.get("Score", 0))
        except (ValueError, TypeError):
            score = 0
        
        languages_str = str(status.get("Languages", ""))
        terms = _parse_language_terms(languages_str)
        
        for term in terms:
            try:
                pattern = re.compile(r'\b' + re.escape(term) + r'\b', re.IGNORECASE)
                _status_patterns.append((pattern, status_id, score))
            except re.error:
                print(f"[ONTOLOGY WARNING] Invalid regex for term '{term}' in status {status_id}")
    
    _loaded = True
    print(f"[ONTOLOGY] Loaded {len(_concept_patterns)} concept patterns and {len(_status_patterns)} status patterns from Google Sheets.")


def extract_concepts(text):
    """
    Extracts semantic concepts from article text.
    
    Returns a list of tuples: [(concept_id, score), ...]
    Each concept is returned at most once even if multiple synonyms match.
    """
    if not _loaded:
        return []
    
    found = {}  # concept_id -> score (deduplicate by concept)
    text_lower = text.lower()
    
    for pattern, concept_id, score in _concept_patterns:
        if concept_id not in found and pattern.search(text_lower):
            found[concept_id] = score
    
    return list(found.items())


def extract_statuses(text):
    """
    Extracts event statuses from article text.
    
    Returns a list of tuples: [(status_id, score), ...]
    Each status is returned at most once.
    """
    if not _loaded:
        return []
    
    found = {}  # status_id -> score (deduplicate by status)
    text_lower = text.lower()
    
    for pattern, status_id, score in _status_patterns:
        if status_id not in found and pattern.search(text_lower):
            found[status_id] = score
    
    return list(found.items())


def get_all_matched_terms(text):
    """
    Returns all raw terms that matched in the text.
    Used for Ontology Review logging.
    
    Returns a list of strings: ["acquisition", "übernahme", ...]
    """
    if not _loaded:
        return []
    
    matched = []
    text_lower = text.lower()
    
    for pattern, _, _ in _concept_patterns + _status_patterns:
        match = pattern.search(text_lower)
        if match:
            matched.append(match.group())
    
    return matched
