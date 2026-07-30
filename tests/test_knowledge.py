import pytest
from src.utils.id_generator import generate_id
from src.knowledge.schemas.core import Event, SourceReliability

def test_deterministic_id_generation():
    assert generate_id("EVENT", "tender-offer") == generate_id("EVENT", "tender-offer")

def test_confidence_math():
    event = Event(
        event_id="EV-1", case_id="CS-1",
        source_reliability=SourceReliability.A,
        extraction_confidence=0.90, research_confidence=0.80
    )
    assert event.calculate_overall_confidence() == 0.684

from src.parsers.document_parser import DocumentParser

def test_document_parsing_separation():
    raw_ai_output = {
        "ticker": "DSGR",
        "event_type": "Merger Announcement",
        "defined_cash_amount": "55.00",
        "extraction_confidence": 0.95,
        "research_confidence": 0.90,
        "premium_vs_market": "22.5%",
        "implied_volatility_skew": "Bullish call demand noted"
    }

    event = DocumentParser.stage_event_from_analysis(
        case_id="CASE-DSGR01",
        source_type="newswire",
        extraction=raw_ai_output
    )

    # Verify hard facts are isolated
    assert event.facts["ticker"] == "DSGR"
    assert event.facts["defined_cash_amount"] == "55.00"
    assert "premium_vs_market" not in event.facts

    # Verify subjective analytics sit safely inside the interpretation block
    assert event.ai_interpretation["premium_vs_market"] == "22.5%"
    assert event.source_reliability.value == "B+"
