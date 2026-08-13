import pytest
import sqlite3
import hashlib
from unittest.mock import patch

from monitor import process_article, PipelineTelemetry
from src.database import initialise_database, DB_PATH, check_event_exists
from src.ai import ProviderRouter

@pytest.fixture(autouse=True)
def setup_db():
    initialise_database()
    yield

def get_mock_config():
    return {
        "settings": [{"Options Tradable Only": "FALSE"}],
        "playbooks": [{"Playbook": "Cash Merger", "Active": "TRUE"}],
        "global_exclusions": []
    }

def get_base_article(test_id: str, title: str):
    body = f"Test body {test_id}"
    art = {
        "headline": title,
        "url": f"http://test.local/{test_id}",
        "body": body,
        "source": "test_source",
        "channel": "test_channel"
    }
    art["article_hash"] = hashlib.md5(f"test_source::{title.lower()}".encode('utf-8')).hexdigest()
    return art

def assert_registry_state(article_hash: str, expect_registry: bool, expect_ledger: bool):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    cur.execute("SELECT event_id FROM event_registry WHERE article_hash = ?", (article_hash,))
    reg_row = cur.fetchone()
    
    if expect_registry:
        assert reg_row is not None, "Expected in event_registry, but not found."
        
        cur.execute("SELECT detection_outcome FROM evaluation_ledger WHERE event_id = ?", (reg_row[0],))
        led_row = cur.fetchone()
        
        if expect_ledger:
            assert led_row is not None, "Expected in evaluation_ledger, but not found."
        else:
            assert led_row is None, "Expected NOT in evaluation_ledger, but found."
    else:
        assert reg_row is None, "Expected NOT in event_registry, but found."
        
    conn.close()

def test_a_crash_retry_processable():
    """A. Crash test: processing exception -> neither ledger nor event_registry -> retry remains processable."""
    art = get_base_article("A", "Crash Test Article")
    telemetry = PipelineTelemetry()
    
    # Mock a crash during stage_ontology_concepts
    with patch('monitor.stage_ontology_concepts', side_effect=ValueError("Simulated Crash")):
        try:
            process_article(art.copy(), telemetry, get_mock_config(), "HASH", ProviderRouter())
        except ValueError:
            pass # Caught in main loop normally
            
    assert_registry_state(art["article_hash"], expect_registry=False, expect_ledger=False)
    
    # Retry should NOT be dropped as duplicate
    _, is_new = check_event_exists(art["article_hash"])
    assert is_new is True, "Article should be considered new on retry after a crash."

def test_b_legitimate_drop():
    """B. Legitimate DROP: terminal business-rule drop -> both terminal ledger and event identity persist."""
    art = get_base_article("B", "Legitimate Drop Article")
    telemetry = PipelineTelemetry()
    
    # Mock a legitimate drop (stage returns False)
    with patch('monitor.stage_ontology_concepts', return_value=(False, "dropped_ontology_score")):
        process_article(art.copy(), telemetry, get_mock_config(), "HASH", ProviderRouter())
        
    assert_registry_state(art["article_hash"], expect_registry=True, expect_ledger=True)
    
    # Existing committed identity should correctly produce dropped_hash_duplicate on next run
    _, is_new = check_event_exists(art["article_hash"])
    assert is_new is False, "Article should be considered duplicate after a legitimate drop."

def test_c_legitimate_alert():
    """C. Legitimate ALERT: successful alert -> both persist."""
    art = get_base_article("C", "Legitimate Alert Article")
    telemetry = PipelineTelemetry()
    
    # Mock all stages passing
    with patch('monitor.stage_ontology_concepts', return_value=(True, "passed")), \
         patch('monitor.stage_ai_classification', return_value=(True, "passed", {"target_ticker": "TGT", "event_type": "Merger", "confidence": "HIGH", "analysis": "foo", "validated_trades": {}})), \
         patch('monitor.stage_ticker_resolution', return_value=(True, "passed")), \
         patch('monitor.stage_ai_ticker_resolution', return_value=(True, "passed")):
         
        with patch('monitor.send_alert', return_value=True):
            process_article(art.copy(), telemetry, get_mock_config(), "HASH", ProviderRouter())
            
    assert_registry_state(art["article_hash"], expect_registry=True, expect_ledger=True)
    
    _, is_new = check_event_exists(art["article_hash"])
    assert is_new is False, "Article should be considered duplicate after an alert."

def test_d_crash_then_retry_success():
    """D. Crash/retry test: first attempt crashes; second attempt successfully reaches terminal outcome."""
    art = get_base_article("D", "Crash Then Success Article")
    telemetry = PipelineTelemetry()
    
    # Attempt 1: Crash
    with patch('monitor.stage_ontology_concepts', side_effect=ValueError("Simulated Crash")):
        try:
            process_article(art.copy(), telemetry, get_mock_config(), "HASH", ProviderRouter())
        except ValueError:
            pass
            
    assert_registry_state(art["article_hash"], expect_registry=False, expect_ledger=False)
    
    # Attempt 2: Success
    with patch('monitor.stage_ontology_concepts', return_value=(False, "dropped_business_rule")):
        process_article(art.copy(), telemetry, get_mock_config(), "HASH", ProviderRouter())
        
    assert_registry_state(art["article_hash"], expect_registry=True, expect_ledger=True)
    
    # Attempt 3: Dedupe prevents processing
    _, is_new = check_event_exists(art["article_hash"])
    assert is_new is False, "Article should be duplicate on third run."
