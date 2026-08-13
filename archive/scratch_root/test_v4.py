import datetime
from src.database import log_audit_source_metrics, log_audit_ai_metrics

run_id = "RUN-V4-TEST-001"

# Fake ingestion ledger
ledger = [
    {"source": "PR Newswire", "channel": "HTML", "raw_found": 20000, "unique_found": 8000, 
     "metadata": {"pages_visited": 200, "page_limit": 200, "checkpoint_found": False, "emergency_stop": True, "reason": "Hit 20,000 limit"}},
    {"source": "GlobeNewswire", "channel": "HTML", "raw_found": 4500, "unique_found": 1200, 
     "metadata": {"pages_visited": 45, "page_limit": 200, "checkpoint_found": True, "emergency_stop": False, "reason": ""}},
    {"source": "Business Wire", "channel": "RSS", "raw_found": 3500, "unique_found": 800, 
     "metadata": {"pages_visited": 1, "page_limit": 1, "checkpoint_found": True, "emergency_stop": False, "reason": ""}}
]

log_audit_source_metrics(run_id, ledger)

# Fake AI telemetry
ai_metrics = [
    {"provider": "gemini", "prompt_type": "Ticker Extraction", "input_tokens": 1500, "output_tokens": 4, "latency_ms": 1200, "cost": 0.0001, "success": True},
    {"provider": "gemini", "prompt_type": "Event Classification", "input_tokens": 2000, "output_tokens": 45, "latency_ms": 2100, "cost": 0.0002, "success": True},
    {"provider": "gemini", "prompt_type": "Event Classification", "input_tokens": 0, "output_tokens": 0, "latency_ms": 4000, "cost": 0, "success": False}
] * 150

log_audit_ai_metrics(run_id, ai_metrics)
print("Populated ssr_audit.db with fake V4 data")
