import sys
import logging
from monitor import PipelineTelemetry, process_article, STAGE_REGISTRY, _record_screening
from src.database import initialise_database, save_workflow_health
import time
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)
initialise_database()

telemetry = PipelineTelemetry()
article = {
    "headline": "TEST ACQUISITION: Apple Acquires Microsoft for $2 Trillion",
    "body": "Apple (NASDAQ: AAPL) announced today it will acquire Microsoft in a 100% cash transaction.",
    "source": "PR Newswire",
    "url": "http://test",
    "_ingestion_mode": "HTML",
    "document_type": "Press Release"
}

# We need a valid config manifest
config_manifest = {
    "sys_settings": {"MIN_ONTOLOGY_SCORE": 0.0, "MIN_AI_CONFIDENCE": 0.0, "Options Tradable Only": "False"},
    "semantic_concepts": [],
    "rules": [],
    "playbooks": [{"Playbook": "merger", "Active": "TRUE"}],
    "sources": []
}

# Mocking all external calls for speed
def mock_evaluate_ontology_rich(text): return {"score": 1.0, "matched": ["acquisition"]}
import src.ontology
src.ontology.engine.evaluate_ontology_rich = mock_evaluate_ontology_rich
import monitor
monitor.evaluate_ontology_rich = mock_evaluate_ontology_rich

def mock_evaluate_deterministic_rules(*args, **kwargs):
    return [{"Rule": "merger", "Score": 10.0}]
monitor.evaluate_deterministic_rules = mock_evaluate_deterministic_rules

def mock_get_t12_metrics(ticker): return {"valid": True, "average_volume": 1000000}
monitor.get_t12_metrics = mock_get_t12_metrics

def mock_query_financial_snapshot(ticker): pass
monitor.query_financial_snapshot = mock_query_financial_snapshot

def mock_extract_target_ticker(text): return "AAPL"
monitor.extract_target_ticker = mock_extract_target_ticker

def mock_classify_event(text, ticker): return {"status": "SUCCESS", "classification": "merger", "confidence": 0.99}
monitor.classify_event = mock_classify_event

def mock_send_alert(manifest): print("EMAIL SENT TO", manifest["target_ticker"])
monitor.send_alert = mock_send_alert

monitor.batch_append_daily_memory = lambda *args: None
monitor.append_to_research_queue = lambda *args: None

# Override pipeline to the one we want to test
config_manifest["pipeline"] = []

print("Running fast test...")
process_article(article, telemetry, config_manifest, "CFG-TEST")

health_payload = {
    "run_id": telemetry.run_id,
    "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT"),
    "funnel": telemetry.stage_analytics
}
save_workflow_health(health_payload)
print(f"Saved run {telemetry.run_id}")
