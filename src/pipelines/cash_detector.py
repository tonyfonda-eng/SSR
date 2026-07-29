import json
from typing import List, Optional
from src.providers.router import AI
from src.utils.id_generator import generate_id
from src.knowledge.schemas.core import Announcement, CorporateAction, Event

class CashEventDetector:
    @staticmethod
    def inspect_announcement(announcement: Announcement) -> Optional[List[dict]]:
        """
        SSR's Alpha Engine: Upfront strategy-independent check.
        Asks: 'Does this announcement contain any future defined cash event?'
        """
        print("[Cash Event Detector] Processing top-of-funnel discovery scan...")
        
        detection_prompt = """
        You are SSR's strategic Alpha Engine. Inspect the text for any future defined cash events 
        (e.g. cash mergers, tender offers, special dividends, liquidations).
        Return a valid JSON object with EXACTLY one key: "cash_events_found".
        This key must hold a list of objects. If no events exist, return an empty list [].
        Each event object must contain these keys:
        - ticker (string)
        - company_name (string)
        - potential_ontology_type (string e.g. Cash Merger, Special Dividend)
        - target_cash_value (string or null)
        - extraction_confidence (float 0.0 to 1.0)
        - completeness_score (float 0.0 to 1.0)
        - option_notes (string or null)
        """
        
        try:
            raw_analysis = AI.route(task="research", payload=announcement.raw_text)
            if isinstance(raw_analysis, dict) and "cash_events_found" in raw_analysis:
                return raw_analysis["cash_events_found"]
            return [raw_analysis]
        except Exception as e:
            print(f"[Cash Event Detector] Analysis encountered routing error: {e}")
            return None

    @staticmethod
    def process_pipeline(announcement: Announcement) -> List[Event]:
        """Orchestrates the Announcement -> Corporate Action -> Atomic Events model."""
        detected_items = CashEventDetector.inspect_announcement(announcement)
        if not detected_items:
            print("[Cash Event Detector] 0 Cash Events discovered. Ingress discarded safely.")
            return []
            
        staged_events = []
        for index, item in enumerate(detected_items):
            ticker = item.get("ticker", "UNKNOWN").upper()
            company = item.get("company_name", "UNKNOWN")
            
            # Establish IDs
            action_id = generate_id("ACTION", f"{ticker}-{announcement.discovered_at.strftime('%Y%m%d')}")
            event_id = generate_id("EVENT", f"{action_id}-E{index}")
            
            facts_layer = {
                "ticker": ticker,
                "company_name": company,
                "defined_cash_amount": item.get("target_cash_value")
            }
            
            interpretation_layer = {
                "detected_type": item.get("potential_ontology_type"),
                "option_chain_telemetry": item.get("option_notes")
            }
            
            atomic_event = Event(
                event_id=event_id,
                action_id=action_id,
                announcement_quality=announcement.announcement_quality,
                source_reliability=announcement.source_reliability,
                extraction_confidence=item.get("extraction_confidence", 1.0),
                event_completeness=item.get("completeness_score", 1.0),
                research_confidence=0.90,
                facts=facts_layer,
                ai_interpretation=interpretation_layer
            )
            staged_events.append(atomic_event)
            
        return staged_events
