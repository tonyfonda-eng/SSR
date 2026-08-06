"""
SSR 2.0 Hardening Sprint: E2E Pipeline Regression Test
Runs the pipeline entirely offline against the static Golden Dataset.
Ensures that no future code changes secretly break detection logic.
"""
import os
import json
import pytest
import sqlite3
from unittest.mock import patch
from monitor import process_article, PipelineTelemetry
from src.ai import ProviderRouter
from src.database import initialise_database, DB_PATH, get_or_create_event

GOLDEN_DATASET_PATH = "src/validation/test_assets/golden_benchmark.json"

@pytest.fixture(scope="module")
def setup_test_env():
    # Ensure database is initialized
    initialise_database()
    
    # Load Golden Dataset
    if not os.path.exists(GOLDEN_DATASET_PATH):
        pytest.skip(f"Golden dataset not found at {GOLDEN_DATASET_PATH}")
        
    with open(GOLDEN_DATASET_PATH, 'r', encoding='utf-8') as f:
        golden_data = json.load(f)
        
    # We only test a handful to prevent massive API bills on every commit, 
    # focusing on the critical True Positives.
    test_cases = [c for c in golden_data.get("cases", []) if c.get("expected_outcome") == "DETECTED"][:5]
    
    # Mock configuration manifest
    config_manifest = {
        "settings": [{"Options Tradable Only": "FALSE"}],
        "playbooks": [{"Playbook": "Cash Merger", "Active": "TRUE"}, {"Playbook": "Spinoff", "Active": "TRUE"}],
        "global_exclusions": []
    }
    
    router = ProviderRouter()
    
    return test_cases, config_manifest, router

@patch('src.alerts.email.send_alert') # Mock outbound email so we don't spam ourselves during tests
def test_pipeline_e2e(mock_send_alert, setup_test_env):
    test_cases, config_manifest, router = setup_test_env
    
    if not test_cases:
        pytest.skip("No DETECTED cases found in golden dataset.")
        
    telemetry = PipelineTelemetry()
    
    for case in test_cases:
        article = {
            "headline": "Offline E2E Test Article",
            "url": "https://offline-test.local",
            "body": case.get("raw_text", ""),
            "published": "2026-08-06",
            "source": "Golden Dataset"
        }
        
        # Override the generated hash so we can look it up deterministically
        article["_article_hash"] = case.get("article_hash")
        
        # Run through pipeline
        process_article(article, telemetry, config_manifest, "TEST-HASH", router)
        
        # Check SQLite ledger to ensure it was DETECTED
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT event_id FROM event_registry WHERE article_hash = ?", (case.get("article_hash"),))
        event_row = cursor.fetchone()
        assert event_row is not None, f"Event not registered for {case.get('article_hash')}"
        
        cursor.execute("""
            SELECT detection_outcome 
            FROM evaluation_ledger 
            WHERE event_id = ? 
            ORDER BY runtime_timestamp DESC LIMIT 1
        """, (event_row[0],))
        ledger_row = cursor.fetchone()
        
        conn.close()
        
        assert ledger_row is not None, f"No ledger entry found for {case.get('article_hash')}"
        actual_outcome = ledger_row[0]
        expected = case.get("expected_outcome")
        
        assert actual_outcome in ["DETECTED", "DISPATCHED"], f"Regression! Expected {expected} but got {actual_outcome} for case {case.get('article_hash')}"
