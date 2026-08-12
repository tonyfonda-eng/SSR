import os
from src.alerts.email import send_alert
from src.database import _get_connection, AUDIT_DB_PATH, initialise_database

initialise_database()
print("Testing Email Dispatch...")

# A valid dummy decision manifest matching the expected structure
manifest = {
    "decision_id": "DEC-TEST-001",
    "event_id": "EVT-TEST-001",
    "manifest_hash": "dummy_hash_123",
    "runtime_timestamp": "2026-08-12 18:00:00 GMT",
    "detection_outcome": "DETECTED",
    "terminal_stage": "AI_APPROVED",
    "headline": "TEST EVENT: Controlled End-to-End Delivery",
    "url": "http://localhost/test",
    "event_type": "Merger/Acquisition",
    "target_ticker": "TEST",
    "research_summary": "This is a controlled end-to-end test to verify SMTP telemetry.",
    "ai_core_inference": {
        "aggregate_confidence": 0.99
    },
    "evidence": [
        {"component": "System Test", "assertion": "Testing SMTP flow", "weight": 1.0}
    ]
}

# Ensure env vars are loaded (similar to github actions)
# Assuming GMAIL_USER / GMAIL_APP_PASSWORD will fallback to local config/secrets if set, or we can rely on secrets.py
import src.config.secrets

print(f"Credentials loaded for: {src.config.secrets.GMAIL_USER}")

try:
    send_alert(manifest)
    print("Alert sent successfully (or at least no crash).")
except Exception as e:
    print(f"Failed during send_alert: {e}")

# Check telemetry
print("\n--- Telemetry from email_dispatch_log ---")
conn = _get_connection(AUDIT_DB_PATH)
cursor = conn.cursor()
cursor.execute("SELECT timestamp, outcome_state, exception_class, provider_response FROM email_dispatch_log WHERE decision_id = 'DEC-TEST-001'")
rows = cursor.fetchall()
for row in rows:
    print(row)
conn.close()
