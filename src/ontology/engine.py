"""
SSR 2.0: Ontology & Taxonomy Extraction Engine (Layer B - Derived Facts)
Executes tokenization and semantic matching against raw ingested text.
Outputs deterministic evidence records with strict causal text offsets.
"""

import logging
import re
from dataclasses import dataclass
from typing import List, Tuple

# NEW: Import directly from our robust sheets client instead of the old utils folder
from src.sheets import load_semantic_concepts, load_event_statuses

logger = logging.getLogger(__name__)

# In-memory caches for the active execution manifest
_KNOWLEDGE_GRAPH = {}
_STATUS_GRAPH = {}
_ACTIVE_ONTOLOGY_VERSION = "2.0.0"


@dataclass
class ConceptMatch:
    """Deterministic causal node representing an ontology match."""
    concept_id: str
    confidence: float
    matched_string: str
    text_start_offset: int
    text_end_offset: int


def load_ontology(sheet_url: str) -> None:
    """
    Initializes the semantic dictionary using the unified SSR 2.0 Sheets client.
    """
    global _KNOWLEDGE_GRAPH, _STATUS_GRAPH
    logger.info("[ONTOLOGY] Bootstrapping semantic taxonomy from master configuration.")
    try:
        # Use our new centralized sheet loaders!
        concepts = load_semantic_concepts(sheet_url)
        statuses = load_event_statuses(sheet_url)
        
        # Load Core Concepts
        for row in concepts:
            if str(row.get("Active", "TRUE")).upper() == "TRUE":
                cid = row.get("Concept ID", row.get("ConceptID"))
                # Handle different potential column names for Keywords
                raw_keywords = row.get("Keywords", row.get("Phrases", ""))
                phrases = [p.strip() for p in str(raw_keywords).split(",") if p.strip()]
                weight = float(row.get("Weight", 1.0))
                
                if cid and phrases:
                    _KNOWLEDGE_GRAPH[cid] = {"phrases": phrases, "weight": weight}

        # Load Deal Statuses
        for row in statuses:
            if str(row.get("Active", "TRUE")).upper() == "TRUE":
                sid = row.get("Status ID", row.get("StatusID", row.get("Event Status", "")))
                raw_keywords = row.get("Keywords", row.get("Phrases", ""))
                phrases = [p.strip() for p in str(raw_keywords).split(",") if p.strip()]
                
                if sid and phrases:
                    _STATUS_GRAPH[sid] = {"phrases": phrases}
                
        logger.info(f"[ONTOLOGY] Initialization complete. Loaded {len(_KNOWLEDGE_GRAPH)} concepts and {len(_STATUS_GRAPH)} statuses.")
    except Exception as e:
        logger.error(f"[ONTOLOGY ERROR] Taxonomy bootstrap failed: {e}")


def extract_concepts(raw_text: str) -> List[Tuple[str, float]]:
    matches = get_concept_matches(raw_text)
    deduped = {}
    for m in matches:
        if m.concept_id not in deduped or m.confidence > deduped[m.concept_id]:
            deduped[m.concept_id] = m.confidence
    return list(deduped.items())


def extract_statuses(raw_text: str) -> List[str]:
    if not raw_text:
        return []
    text_lower = raw_text.lower()
    matches = set()
    for sid, data in _STATUS_GRAPH.items():
        for phrase in data["phrases"]:
            if re.search(r'\b' + re.escape(phrase.lower()) + r'\b', text_lower):
                matches.add(sid)
                break 
    return list(matches)


def get_all_matched_terms(raw_text: str) -> List[str]:
    matches = get_concept_matches(raw_text)
    return list(set([m.matched_string for m in matches]))


def get_concept_matches(raw_text: str) -> List[ConceptMatch]:
    matches = []
    if not raw_text:
        return matches
    for cid, data in _KNOWLEDGE_GRAPH.items():
        weight = data.get("weight", 1.0)
        for phrase in data.get("phrases", []):
            if not phrase: continue
            try:
                for match in re.finditer(r'\b' + re.escape(phrase) + r'\b', raw_text, re.IGNORECASE):
                    matches.append(ConceptMatch(
                        concept_id=cid,
                        confidence=weight,
                        matched_string=match.group(0),
                        text_start_offset=match.start(),
                        text_end_offset=match.end()
                    ))
            except re.error as e:
                logger.debug(f"Invalid ontology regex pattern '{phrase}': {e}")
    return matches
