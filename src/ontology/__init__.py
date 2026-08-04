from .engine import load_ontology, extract_concepts, get_concept_matches

def evaluate_ontology(raw_text: str, semantic_concepts: list = None) -> float:
    """
    Evaluates the text against the active ontology graph.
    Returns the total aggregate weight of all matched semantic concepts.
    """
    if not raw_text:
        return 0.0
        
    matches = extract_concepts(raw_text)
    # matches is a list of tuples: (ConceptID, Weight)
    return sum(weight for _, weight in matches)
