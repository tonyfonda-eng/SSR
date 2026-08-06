import os
import sys

# Ensure project root is in PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.alerts.email import send_alert
from src.config.secrets import GMAIL_USER, GMAIL_APP_PASSWORD

def main():
    if not GMAIL_USER or not GMAIL_APP_PASSWORD or GMAIL_USER == "your-email@gmail.com":
        print("[FAIL] Missing or invalid Gmail credentials in .env")
        sys.exit(1)
        
    print(f"Testing email dispatch using {GMAIL_USER}...")
    
    mock_capsule = {
        "manifest_registry": {
            "decision_id": "DEC-TEST001",
            "execution_timestamp_gmt": "2026-08-06 12:00:00 GMT",
            "configuration_manifest_hash": "CFG-MOCKHASH"
        },
        "detection_vector": {
            "detected_event_type": "Merger",
            "target_ticker": "TEST",
            "confidence_decomposition": {
                "aggregate_confidence": 0.95
            }
        },
        "evidentiary_provenance_dag": {
            "supporting_evidence": [
                {
                    "component": "Rule engine",
                    "assertion": "Matched merger terminology",
                    "weight": 5.0
                }
            ]
        },
        "syndication_lineage": {
            "canonical_sensor_id": "TestSensor"
        },
        "headline": "TEST INC ANNOUNCES MERGER WITH DUMMY CORP",
        "url": "http://localhost/test",
        "research_summary": "This is a decoupled email test verifying SMTP functionality.",
        "is_update": False
    }

    try:
        recipient = os.environ.get("ALERT_EMAIL_RECIPIENT", GMAIL_USER)
        send_alert(mock_capsule, recipient)
        print("[SUCCESS] Test email dispatched without errors.")
    except Exception as e:
        print(f"[FAIL] Error dispatching test email: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
