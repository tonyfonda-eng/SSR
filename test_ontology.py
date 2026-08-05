from src.ontology.engine import load_ontology, extract_detailed_concepts
from src.config.settings import SHEET_URL

load_ontology(SHEET_URL)
text = "The company announced a definitive agreement to acquire the entire share capital of Target Corp."
print(extract_detailed_concepts(text))
