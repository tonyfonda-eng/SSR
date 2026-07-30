from typing import Dict, Any
from src.utils.id_generator import generate_id
from src.knowledge.schemas.core import Article, Event, SourceReliability, LifecycleStatus

class DocumentParser:
    @staticmethod
    def create_article(source_url: str, raw_content: str) -> Article:
        """Wraps raw ingested text into a standard Article object with a unique ID."""
        article_id = generate_id("ARTICLE", seed=source_url + raw_content[:50])
        return Article(
            article_id=article_id,
            source_url=source_url,
            raw_content=raw_content
        )

    @staticmethod
    def stage_event_from_analysis(case_id: str, source_type: str, extraction: Dict[str, Any]) -> Event:
        """
        Transforms raw AI extraction outputs into the strict Canonical Event structure.
        Enforces separation between hard structural facts and analytical interpretations.
        """
        # Map source strings to standard constitutional reliability grades
        source_mapping = {
            "sec_filing": SourceReliability.A_PLUS,
            "company_ir": SourceReliability.A,
            "exchange_announcement": SourceReliability.A_MINUS,
            "newswire": SourceReliability.B_PLUS,
            "media": SourceReliability.C
        }
        reliability = source_mapping.get(source_type.lower(), SourceReliability.C)
        
        # Generate a unique deterministic ID for the event context
        seed_str = f"{case_id}_{extraction.get('ticker', 'UNKNOWN')}_{extraction.get('event_type', 'EVENT')}"
        event_id = generate_id("EVENT", seed=seed_str)

        # Separate hard structural attributes from interpretations
        facts_keys = {"ticker", "event_type", "announcement_date", "defined_cash_amount", "effective_date"}
        facts_dict = {k: v for k, v in extraction.items() if k in facts_keys}
        ai_dict = {k: v for k, v in extraction.items() if k not in facts_keys}

        return Event(
            event_id=event_id,
            case_id=case_id,
            lifecycle_status=LifecycleStatus.CLASSIFIED,
            source_reliability=reliability,
            extraction_confidence=extraction.get("extraction_confidence", 0.5),
            research_confidence=extraction.get("research_confidence", 0.5),
            facts=facts_dict,
            ai_interpretation=ai_dict,
            human_decision={}
        )
