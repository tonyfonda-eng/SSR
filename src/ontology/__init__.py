"""
Corporate Action Ontology — public API.

Exposes the sheet-driven concept and status extraction engine.
Replaces the per-country hardcoded dictionaries (germany.py, france.py, etc.)
"""
from .concepts import load_ontology, extract_concepts, extract_statuses, get_all_matched_terms
