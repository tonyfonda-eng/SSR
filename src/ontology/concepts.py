"""
Corporate Action Ontology — Sheet-Driven Concept Extraction.
Optimized for high-throughput regex alternation and Unicode normalization.
"""
import re
import unicodedata
import logging

logger = logging.getLogger(__name__)

# Module-level cache: populated once at startup by load_ontology()
_concept_patterns = []   # [(compiled_regex, concept_id, score), ...]
_status_patterns = []    # [(compiled_regex, status_id, score), ...]
_loaded = False


def _parse_language_terms(languages_str):
    """
    Parses the Languages column from Google Sheets into a list of cleaned term strings.
    Expected format:
        "English: acquisition, purchase, takeover; German: übernahme; French: acquisition"
    """
    terms = []
    if not languages_str:
        return terms
    
    blocks = languages_str.split(";")
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        
        if ":" in block:
            _, term_part = block.split(":", 1)
        else:
            term_part = block
        
        for term in term_part.split(","):
            term = term.strip().lower()
            if term:
                # Normalize unicode terms upon ingestion
                normalized_term = unicodedata.normalize('NFKC', term)
                terms.append(normalized_term)
    
    return terms


def load_ontology(sheet_url):
    """
    Loads semantic concepts and event statuses from Google Sheets.
    Builds consolidated regex alternation patterns for lightning-fast multi-language extraction.
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
        
        if terms:
            try:
                # PERFORMANCE OPTIMIZATION: Combine all synonym terms into a single alternation regex
                escaped_terms = sorted(list(set(re.escape(t) for t in terms)), key=len, reverse=True)
                pattern_str = r'\b(' + '|'.join(escaped_terms) + r')\b'
                compiled_pattern = re.compile(pattern_str, re.IGNORECASE)
                _concept_patterns.append((compiled_pattern, concept_id, score))
            except re.error as e:
                logger.warning(f"[ONTOLOGY WARNING] Invalid regex compilation for concept {concept_id}: {e}")
    
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
        
        if terms:
            try:
                escaped_terms = sorted(list(set(re.escape(t) for t in terms)), key=len, reverse=True)
                pattern_str = r'\b(' + '|'.join(escaped_terms) + r')\b'
                compiled_pattern = re.compile(pattern_str, re.IGNORECASE)
                _status_patterns.append((compiled_pattern, status_id, score))
            except re.error as e:
                logger.warning(f"[ONTOLOGY WARNING] Invalid regex compilation for status {status_id}: {e}")
    
    _loaded = True
    print(f"[ONTOLOGY] Loaded {len(_concept_patterns)} consolidated concept patterns and {len(_status_patterns)} status patterns from Google Sheets.")


def extract_concepts(text):
    """
    Extracts semantic concepts from article text using optimized consolidated patterns.
    Returns a list of tuples: [(concept_id, score), ...]
    """
    if not _loaded:
        logger.warning("[ONTOLOGY] extract_concepts called before ontology was loaded.")
        return []
    
    if not text:
        return []
    
    # Unicode normalize input text to ensure robust diacritic matching
    text_normalized = unicodedata.normalize('NFKC', text.lower())
    found = {}
    
    for pattern, concept_id, score in _concept_patterns:
        if concept_id not in found and pattern.search(text_normalized):
            found[concept_id] = score
    
    return list(found.items())


def extract_statuses(text):
    """
    Extracts event statuses from article text using optimized consolidated patterns.
    Returns a list of tuples: [(status_id, score), ...]
    """
    if not _loaded:
        logger.warning("[ONTOLOGY] extract_statuses called before ontology was loaded.")
        return []
    
    if not text:
        return []
    
    text_normalized = unicodedata.normalize('NFKC', text.lower())
    found = {}
    
    for pattern, status_id, score in _status_patterns:
        if status_id not in found and pattern.search(text_normalized):
            found[status_id] = score
    
    return list(found.items())


def get_all_matched_terms(text):
    """
    Returns all raw terms that matched in the text.
    Used for Ontology Review logging.
    """
    if not _loaded or not text:
        return []
    
    matched = []
    text_normalized = unicodedata.normalize('NFKC', text.lower())
    
    for pattern, _, _ in _concept_patterns + _status_patterns:
        matches = pattern.findall(text_normalized)
        for m in matches:
            # pattern.findall returns the group(1) capture for alternation, or string match
            term = m[0] if isinstance(m, tuple) else m
            if term and term not in matched:
                matched.append(term)
    
    return matched