"""
SSR 2.0: Ontology & Taxonomy Extraction Engine (Layer B - Derived Facts)
Executes tokenization and semantic matching against raw ingested text.
Outputs deterministic evidence records with strict causal text offsets.
"""

import json
import logging
import re
from dataclasses import dataclass
from typing import List, Dict, Tuple, Any
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from src.config.secrets import get_google_service_account

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


def get_sheets_service():
    """Initializes the Google Sheets API client service."""
    try:
        creds_dict = get_google_service_account()
        scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        return build('sheets', 'v4', credentials=creds)
    except Exception as e:
        logger.error(f"[ONTOLOGY] Failed to build Google Sheets service: {e}")
        return None


def load_ontology(sheet_url: str) -> None:
    """
    Initializes the semantic dictionary.
    In SSR 2.0, this state forms part of the Configuration Manifest.
    """
    global _KNOWLEDGE_GRAPH, _STATUS_GRAPH
    logger.info("[ONTOLOGY] Bootstrapping semantic taxonomy from master configuration.")
    try:
        service = get_sheets_service()
        if not service:
            logger.warning("[ONTOLOGY] Google Sheets service unavailable. Running with empty taxonomy.")
            return

        sheet_id = sheet_url.split('/d/')[1].split('/')[0]
        sheet = service.spreadsheets()
        
        # Load Core Concepts (Aligned with 'Semantic Concepts' tab)
        try:
            concept_res = sheet.values().get(spreadsheetId=sheet_id, range="'Semantic Concepts'!A2:E").execute()
            for row in concept_res.get('values', []):
                if len(row) >= 4 and str(row[3]).strip().upper() == "TRUE":
                    cid = row[0]
                    phrases = [p.strip() for p in row[2].split(",") if p.strip()]
                    weight = float(row[4]) if len(row) > 4 and row[4] else 1.0
                    _KNOWLEDGE_GRAPH[cid] = {"phrases": phrases, "weight": weight}
        except Exception as e:
            logger.warning(f"[ONTOLOGY] Semantic Concepts tab fetch failed: {e}")

        # Load Deal Statuses (Aligned with 'Event Status' tab)
        try:
            status_res = sheet.values().get(spreadsheetId=sheet_id, range="'Event Status'!A2:D").execute()
            for row in status_res.get('values', []):
                if len(row) >= 3 and str(row[2]).strip().upper() == "TRUE":
                    sid = row[0]
                    phrases = [p.strip() for p in row[1].split(",") if p.strip()]
                    _STATUS_GRAPH[sid] = {"phrases": phrases}
        except Exception as e:
            logger.warning(f"[ONTOLOGY] Event Status tab fetch failed: {e}")
            
        logger.info(f"[ONTOLOGY] Initialization complete. Loaded {len(_KNOWLEDGE_GRAPH)} concepts and {len(_STATUS_GRAPH)} statuses.")
    except Exception as e:
        logger.error(f"[ONTOLOGY ERROR] Taxonomy bootstrap failed: {e}")

def extract_concepts(raw_text: str) -> List[Tuple[str, float]]:
    """
    Legacy wrapper for `monitor.py` compatibility.
    Returns a list of tuples: (ConceptID, Weight/Confidence).
    """
    matches = get_concept_matches(raw_text)
    deduped = {}
    for m in matches:
        if m.concept_id not in deduped or m.confidence > deduped[m.concept_id]:
            deduped[m.concept_id] = m.confidence
    return list(deduped.items())


def extract_statuses(raw_text: str) -> List[str]:
    """
    Legacy wrapper for status extraction.
    Returns a list of matched status strings.
    """
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
    """
    Legacy wrapper returning exact string matches for debug logging.
    """
    matches = get_concept_matches(raw_text)
    return list(set([m.matched_string for m in matches]))


def get_concept_matches(raw_text: str) -> List[ConceptMatch]:
    """
    SSR 2.0 Core Method:
    Evaluates the taxonomy against the payload, returning strict causal boundaries.
    """
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