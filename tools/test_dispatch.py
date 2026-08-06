"""
SSR 2.0 Hardening Sprint: Standalone Outbound Dispatcher Test
Verifies SMTP Email and Google Sheets connectivity mathematically.
"""
import sys
import os
import unittest.mock
from src.alerts.email import send_alert
from src.sheets_sync import sync_metrics_to_google_sheets

def test_smtp_connection():
    print("\n[PHASE 1] Testing SMTP Email Dispatch...")
    fake_decision = {
        "manifest_registry": {
            "decision_id": "TEST-DISPATCH-001",
            "execution_timestamp_gmt": "2026-08-06 14:00:00 GMT",
            "configuration_manifest_hash": "TEST-HASH-123"
        },
        "detection_vector": {
            "detected_event_type": "Cash Merger",
            "target_ticker": "AAPL",
            "confidence_decomposition": {"aggregate_confidence": 0.99}
        },
        "evidentiary_provenance_dag": {
            "supporting_evidence": [{"component": "Dry-Run-Script", "assertion": "Testing SMTP Dispatcher", "weight": 1.0}]
        },
        "syndication_lineage": {"canonical_sensor_id": "Dry-Run-Script"},
        "headline": "Apple acquiring Startup X for $1 Billion in Cash",
        "url": "https://github.com/tonyfonda-eng/SSR",
        "research_summary": "This is a synthetic test alert to verify SMTP connectivity. If you are reading this, the outbound dispatch layer is fully functional.",
        "is_update": False
    }
    
    from src.config.secrets import GMAIL_USER, GMAIL_APP_PASSWORD
    if not GMAIL_USER or not GMAIL_APP_PASSWORD or GMAIL_USER == "your-email@gmail.com":
        print("❌ SMTP Email dispatch failed: Credentials not configured (missing or placeholder).")
        return False

    try:
        send_alert(fake_decision)
        print("✅ SMTP Email dispatch successful.")
    except Exception as e:
        print(f"❌ SMTP Email dispatch failed: {e}")
        return False
    return True

def test_sheets_connection():
    print("\n[PHASE 2] Testing Google Sheets Sync...")
    mock_metrics = {
        "run_id": "TEST-RUN-999",
        "timestamp": "2026-08-06 14:00:00 GMT",
        "success": 1,
        "failed": 0,
        "runtime": 1.0,
        "articles": 1,
        "emails": 1,
        "exception": "Dry-Run Test Connection",
        "workflow_version": "shadow",
        "run_number": 999
    }
    
    try:
        # Mock the DB read so we can inject our fake metrics directly into the Google Sheet
        with unittest.mock.patch('src.sheets_sync.get_latest_run_from_db', return_value=mock_metrics):
            sync_metrics_to_google_sheets()
        print("✅ Google Sheets sync successful.")
    except Exception as e:
        print(f"❌ Google Sheets sync failed: {e}")
        return False
    return True

if __name__ == "__main__":
    print("=== SSR 2.0 Hardening Sprint: Dispatcher Dry-Run ===")
    smtp_ok = test_smtp_connection()
    sheets_ok = test_sheets_connection()
    
    if smtp_ok and sheets_ok:
        print("\n🏆 ALL DISPATCHERS FUNCTIONAL. Outbound silence is purely due to AI/Screening logic.")
        sys.exit(0)
    else:
        print("\n🚨 DISPATCHER FAILURES DETECTED. Check credentials and firewalls.")
        sys.exit(1)
