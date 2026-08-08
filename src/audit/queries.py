import sqlite3
import json

RESEARCH_DB = "ssr_observability.db"
DEVOPS_DB = "ssr_devops.db"
AUDIT_DB = "ssr_audit.db"

def _dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def get_db_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = _dict_factory
    return conn

def get_daily_run_summary(date_str):
    """Fetches run-level summary metrics from workflow_health for a given date."""
    conn = get_db_connection(DEVOPS_DB)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            run_id, 
            timestamp, 
            runtime, 
            total_scanned, 
            articles, 
            errors,
            funnel_telemetry
        FROM workflow_health
        WHERE substr(timestamp, 1, 10) = ?
        ORDER BY timestamp ASC
    """, (date_str,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_daily_stage_funnel(date_str):
    """Aggregates funnel telemetry across all runs for a given date."""
    runs = get_daily_run_summary(date_str)
    aggregate_stages = {}
    
    for run in runs:
        telemetry_raw = run.get('funnel_telemetry', '{}')
        if not telemetry_raw:
            continue
        try:
            telemetry = json.loads(telemetry_raw)
            for stage, metrics in telemetry.items():
                if stage not in aggregate_stages:
                    aggregate_stages[stage] = {
                        'entered': 0, 'passed': 0, 'rejected': 0,
                        'cpu_ms': 0.0, 'network_ms': 0.0, 'api_calls': 0,
                        'drop_reasons': {}
                    }
                
                agg = aggregate_stages[stage]
                agg['entered'] += metrics.get('entered', 0)
                agg['passed'] += metrics.get('passed', 0)
                agg['rejected'] += metrics.get('rejected', 0)
                agg['cpu_ms'] += metrics.get('cpu_ms', 0.0)
                agg['network_ms'] += metrics.get('network_ms', 0.0)
                agg['api_calls'] += metrics.get('api_calls', 0)
                
                for reason, count in metrics.get('drop_reasons', {}).items():
                    agg['drop_reasons'][reason] = agg['drop_reasons'].get(reason, 0) + count
                    
        except json.JSONDecodeError:
            pass
            
    return aggregate_stages

def get_rejections_by_stage(date_str):
    """Counts drop reasons per terminal stage."""
    conn = get_db_connection(RESEARCH_DB)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT final_stage, drop_reason, COUNT(*) as count
        FROM article_screening_log
        WHERE substr(timestamp, 1, 10) = ? AND outcome = 'dropped'
        GROUP BY final_stage, drop_reason
        ORDER BY count DESC
    """, (date_str,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_top_rejected_articles(date_str, limit=50):
    """Finds articles that passed ontology but were dropped later, joining with evaluation_ledger for exact scores."""
    conn = get_db_connection(RESEARCH_DB)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.timestamp, a.source, a.headline, a.ticker, a.company_name, a.final_stage, a.drop_reason, e.ontology_metadata
        FROM article_screening_log a
        LEFT JOIN factual_metadata f ON a.url = f.source_url
        LEFT JOIN evaluation_ledger e ON f.decision_id = e.decision_id
        WHERE substr(a.timestamp, 1, 10) = ? AND a.outcome = 'dropped'
          AND a.final_stage NOT IN ('dedupe_hash', 'global_exclusions', 'ontology_concepts')
        ORDER BY a.timestamp DESC
        LIMIT ?
    """, (date_str, limit))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_source_coverage(date_str):
    """Aggregates ingestion counts and deduplication efficiency by source."""
    conn = get_db_connection(RESEARCH_DB)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT source, ingestion_mode, 
               COUNT(*) as total_articles,
               SUM(CASE WHEN final_stage != 'dedupe_hash' THEN 1 ELSE 0 END) as unique_articles
        FROM article_screening_log
        WHERE substr(timestamp, 1, 10) = ?
        GROUP BY source, ingestion_mode
        ORDER BY total_articles DESC
    """, (date_str,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_alerts_generated(date_str):
    """Retrieves successfully dispatched alerts."""
    conn = get_db_connection(RESEARCH_DB)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT timestamp, source, headline, ticker, company_name, event_family
        FROM article_screening_log
        WHERE substr(timestamp, 1, 10) = ? AND outcome = 'passed'
        ORDER BY timestamp DESC
    """, (date_str,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_historical_source_averages(date_str, days=7):
    """Calculates the historical average number of raw articles per source over the last N days."""
    conn = get_db_connection(RESEARCH_DB)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT source, 
               COUNT(*) as total_articles,
               COUNT(DISTINCT date(timestamp)) as days_active
        FROM article_screening_log
        WHERE substr(timestamp, 1, 10) >= date(?, '-' || ? || ' days')
          AND substr(timestamp, 1, 10) < ?
        GROUP BY source
    """, (date_str, str(days), date_str))
    rows = cursor.fetchall()
    conn.close()
    
    averages = {}
    for r in rows:
        averages[r['source']] = r['total_articles'] / r['days_active'] if r['days_active'] else 0
    return averages

def get_db_integrity():
    """Runs a series of health checks on the relational schema."""
    conn = get_db_connection(RESEARCH_DB)
    cursor = conn.cursor()
    issues = []
    
    cursor.execute("PRAGMA foreign_key_check;")
    fk_errors = cursor.fetchall()
    if fk_errors:
        issues.append(f"Broken Foreign Keys: {len(fk_errors)}")
        
    cursor.execute("SELECT COUNT(*) as cnt FROM evaluation_ledger WHERE manifest_hash NOT IN (SELECT hash FROM config_snapshots)")
    missing_manifests = cursor.fetchone()['cnt']
    if missing_manifests > 0:
        issues.append(f"Missing Configuration Manifests: {missing_manifests}")
        
    conn.close()
    return issues

def get_config_changelog(date_str):
    """Compares today's config snapshot with yesterday's to detect changes."""
    conn = get_db_connection(RESEARCH_DB)
    cursor = conn.cursor()
    # Get latest config for today
    cursor.execute("""
        SELECT config_json FROM config_snapshots 
        WHERE substr(captured_at, 1, 10) = ?
        ORDER BY captured_at DESC LIMIT 1
    """, (date_str,))
    today_row = cursor.fetchone()
    
    # Get latest config for yesterday
    cursor.execute("""
        SELECT config_json FROM config_snapshots 
        WHERE substr(captured_at, 1, 10) = date(?, '-1 day')
        ORDER BY captured_at DESC LIMIT 1
    """, (date_str,))
    yest_row = cursor.fetchone()
    conn.close()
    
    today_config = json.loads(today_row['config_json']) if today_row else {}
    yest_config = json.loads(yest_row['config_json']) if yest_row else {}
    
    return today_config, yest_config

def get_raw_appendix(date_str):
    """Fetches a raw SQL dump of key tables for the appendix."""
    appendix = {}
    
    # DEV DB
    conn_dev = get_db_connection(DEVOPS_DB)
    cursor_dev = conn_dev.cursor()
    cursor_dev.execute("SELECT * FROM workflow_health WHERE substr(timestamp, 1, 10) = ? LIMIT 5", (date_str,))
    appendix['workflow_health'] = cursor_dev.fetchall()
    conn_dev.close()
    
    # RESEARCH DB
    conn_res = get_db_connection(RESEARCH_DB)
    cursor_res = conn_res.cursor()
    
    cursor_res.execute("SELECT id, timestamp, source, ticker, outcome, final_stage FROM article_screening_log WHERE substr(timestamp, 1, 10) = ? LIMIT 5", (date_str,))
    appendix['article_screening_log'] = cursor_res.fetchall()
    
    cursor_res.execute("SELECT decision_id, detection_outcome, terminal_stage, evidence_completeness_score FROM evaluation_ledger WHERE substr(runtime_timestamp, 1, 10) = ? LIMIT 5", (date_str,))
    appendix['evaluation_ledger'] = cursor_res.fetchall()
    
    conn_res.close()
    
    return appendix

def get_audit_source_metrics(date_str):
    conn = get_db_connection(AUDIT_DB)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT source, SUM(raw_found) as total_raw, SUM(unique_found) as total_unique,
               MAX(pages_visited) as max_pages, MAX(page_limit) as page_limit,
               MAX(checkpoint_found) as checkpoint_found, MAX(emergency_stop) as emergency_stop,
               SUM(valid_url_count) as total_valid_url,
               SUM(valid_title_count) as total_valid_title,
               SUM(valid_body_count) as total_valid_body,
               SUM(entered_dedupe_count) as total_entered_dedupe,
               SUM(dedupe_passed_count) as total_dedupe_passed,
               SUM(dedupe_rejected_count) as total_dedupe_rejected,
               GROUP_CONCAT(DISTINCT reason) as reasons
        FROM daily_source_metrics
        WHERE substr(timestamp, 1, 10) = ?
        GROUP BY source
    """, (date_str,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_audit_ai_metrics(date_str):
    conn = get_db_connection(AUDIT_DB)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT provider, prompt_type, SUM(input_tokens) as input_tokens, SUM(output_tokens) as output_tokens,
               AVG(latency_ms) as avg_latency, SUM(cost) as total_cost,
               SUM(CASE WHEN success THEN 1 ELSE 0 END) as successes,
               SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) as failures
        FROM daily_ai_metrics
        WHERE substr(timestamp, 1, 10) = ?
        GROUP BY provider, prompt_type
    """, (date_str,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_audit_events(date_str):
    conn = get_db_connection(AUDIT_DB)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT timestamp, source_or_provider, event_type, severity, details
        FROM audit_events
        WHERE substr(timestamp, 1, 10) = ?
        ORDER BY timestamp ASC
    """, (date_str,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_lifetime_source_reliability():
    conn = get_db_connection(AUDIT_DB)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT source, 
               COUNT(*) as total_days,
               SUM(CASE WHEN emergency_stop = 1 THEN 1 ELSE 0 END) as failure_days
        FROM daily_source_metrics
        GROUP BY source
    """)
    rows = cursor.fetchall()
    conn.close()
    
    reliability = {}
    for r in rows:
        total = r['total_days']
        failures = r['failure_days']
        reliability[r['source']] = 100.0 if total == 0 else max(0, 100.0 - (failures / total * 100.0))
    return reliability

def get_ai_drift_metrics(date_str):
    conn = get_db_connection(AUDIT_DB)
    cursor = conn.cursor()
    
    metrics = {}
    for days in [7, 30, 90]:
        cursor.execute("""
            SELECT AVG(input_tokens + output_tokens) as avg_tokens
            FROM daily_ai_metrics
            WHERE substr(timestamp, 1, 10) >= date(?, '-' || ? || ' days')
              AND substr(timestamp, 1, 10) < ?
        """, (date_str, str(days), date_str))
        row = cursor.fetchone()
        metrics[f"{days}d_tokens"] = row['avg_tokens'] if row and row['avg_tokens'] else 0.0
    conn.close()
    return metrics
