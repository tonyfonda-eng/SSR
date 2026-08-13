from src.ontology import load_ontology
from src.ontology.engine import _KNOWLEDGE_GRAPH
from src.config.settings import SHEET_URL

load_ontology(SHEET_URL)
import json
print(json.dumps(_KNOWLEDGE_GRAPH, indent=2))
