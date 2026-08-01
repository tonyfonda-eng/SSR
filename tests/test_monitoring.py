import pytest
import sqlite3
import datetime
import os
from src.database import (
    get_connection, initialise_database, save_run_metrics, get_yesterdays_metrics,
    DB_PATH, save_lifecycle_logs, perform_housekeeping, get_recent_lifecycle_logs,
    save_exception_log, save_ai_usage, save_source_stats
)
from src.monitoring import MetricsCollector

@pytest.fixture(autouse=True)
def setup_teardown():
    # Use an in-memory DB or temporary file for tests if possible, but our code hardcodes DB_PATH.
    # We will backup the real DB if it exists, use it, and then restore.
    backup_path = str(DB_PATH) + ".bak"
    if DB_PATH.exists():
        os.rename(DB_PATH, backup_path)
    
    initialise_database()
    
    yield
    
    if DB_PATH.exists():
        os.remove(DB_PATH)
    if os.path.exists(backup_path):
        os.rename(backup_path, DB_PATH)

def test_metrics_collector():
    metrics = MetricsCollector.get_instance()
    metrics.reset()
    
    metrics.log_article("123", "Test Source", "http://test.com", "Test Title", "US", "en", "PR", "Test Co", "Event", "Regex", "Passed", "Good", True, 100, "Regex")
    assert metrics.daily["articles_processed_count"] == 1
    assert metrics.daily["reached_ai"] == 1
    
    metrics.log_ai_usage("Google", "G1", True, response_time=1.5)
    assert metrics.daily["ai_calls"] == 1
    assert metrics.daily["ai_successes"] == 1

def test_daily_aggregation():
    run_id = "test_run_1"
    yesterday = (datetime.datetime.utcnow() - datetime.timedelta(days=1)).isoformat()
    
    metrics = {
        "run_id": run_id, "timestamp": yesterday, "downloaded": 100, "unique": 90,
        "duplicates": 10, "passed_regex": 80, "failed_regex": 10, "global_exclusions": 0,
        "ontology_matches": 70, "rules_passes": 60, "rules_failures": 10, "ai_calls": 50,
        "ai_successes": 48, "ai_failures": 2, "playbooks_executed": 40, "emails_sent": 20,
        "rules_score_sum": 500.0, "ai_confidence_sum": 450.0, "articles_processed_count": 90,
        "total_runtime_s": 120.0, "rejected_before_regex": 0, "rejected_by_regex": 10,
        "rejected_by_exclusions": 0, "rejected_by_ontology": 10, "rejected_by_rules": 10,
        "reached_ai": 50
    }
    
    save_run_metrics(metrics)
    
    agg = get_yesterdays_metrics()
    daily_stats = agg["daily_stats"]
    assert daily_stats is not None
    # SUM(downloaded) is index 0
    assert daily_stats[0] == 100
    # SUM(ai_successes) is index 10
    assert daily_stats[10] == 48

def test_drift_detection():
    from src.database import get_30_day_average
    
    # Insert 30 days of dummy data
    for i in range(1, 31):
        dt = (datetime.datetime.utcnow() - datetime.timedelta(days=i)).isoformat()
        metrics = {
            "run_id": f"test_{i}", "timestamp": dt, "downloaded": 100, "unique": 100,
            "duplicates": 0, "passed_regex": 80, "failed_regex": 20, "global_exclusions": 0,
            "ontology_matches": 0, "rules_passes": 50, "rules_failures": 0, "ai_calls": 20,
            "ai_successes": 20, "ai_failures": 0, "playbooks_executed": 0, "emails_sent": 5,
            "rules_score_sum": 0, "ai_confidence_sum": 0, "articles_processed_count": 100,
            "total_runtime_s": 60, "rejected_before_regex": 0, "rejected_by_regex": 0,
            "rejected_by_exclusions": 0, "rejected_by_ontology": 0, "rejected_by_rules": 0,
            "reached_ai": 20
        }
        save_run_metrics(metrics)
        
    avg = get_30_day_average()
    assert avg is not None
    assert avg["downloaded"] == 100
    assert avg["passed_regex"] == 80
    assert avg["emails_sent"] == 5

def test_html_dashboard_generation():
    from src.html_generator import generate_dashboard_html
    import tempfile
    
    logs = [{
        "timestamp": "2026-08-01 12:00:00 UTC", "source": "Test", "title": "Headline",
        "url": "http://test", "country": "US", "language": "en", "document_type": "PR",
        "issuer": "TestCorp", "event_family": "M&A", "pipeline_stage": "Rules", 
        "outcome": "Passed", "reason": "Good", "ai_invoked": 1, "processing_time_ms": 150, "slowest_stage": "AI"
    }]
    
    metrics = MetricsCollector.get_instance()
    
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
        tmp_path = f.name
        
    try:
        generate_dashboard_html(logs, output_path=tmp_path, metrics=metrics, avg_30=None, src_30=None)
        with open(tmp_path, "r") as f:
            content = f.read()
            assert "Headline" in content
            assert "TestCorp" in content
    finally:
        os.remove(tmp_path)
