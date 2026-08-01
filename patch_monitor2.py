import re
import sys
import shutil

shutil.copy2('monitor.py', 'monitor.py.bak2')

with open('monitor.py', 'r') as f:
    content = f.read()

# Replace the end of main from lines 745+

start_marker = "    import time\n    metrics.daily[\"total_runtime_s\"]"

new_end = """    import time
    import sys
    import os
    
    total_runtime = time.perf_counter() - metrics.workflow_start
    metrics.daily["total_runtime_s"] = total_runtime
    
    if total_runtime > 240:
        metrics.daily["anomalies"].add(f"Runtime > 4 mins ({total_runtime:.1f}s)")
        
    print("[MONITORING] Writing operational statistics to SQLite...")
    from src.database import save_lifecycle_logs, prune_lifecycle_logs, get_recent_lifecycle_logs, save_run_metrics, save_ai_usage, save_source_stats, save_workflow_health, save_exception_log
    
    # Save Article Traces
    log_rows = []
    for art_id, trace in metrics.article_traces.items():
        log_rows.append((
            art_id, trace["timestamp"], trace["source"], trace["title"], trace["url"], 
            trace["country"], trace["language"], trace["document_type"], trace["issuer"], 
            trace["event_family"], trace["pipeline_stage"], trace["outcome"], trace["reason"], trace["ai_invoked"], 
            trace["processing_time_ms"]
        ))
    save_lifecycle_logs(log_rows)
    prune_lifecycle_logs(days=14)
    
    # Save Run Metrics
    metrics.daily["run_id"] = metrics.run_id
    metrics.daily["timestamp"] = datetime.datetime.utcnow().isoformat()
    save_run_metrics(metrics.daily)
    
    # Save AI Usage
    ai_rows = []
    for key_id, ai in metrics.ai_telemetry.items():
        ai_rows.append((
            metrics.run_id, metrics.daily["timestamp"], ai["provider"], ai["key_id"], ai["requests"],
            ai["success"], ai["failures"], ai["errors_429"], ai["errors_503"], ai["timeouts"],
            ai["retries"], ai["fallbacks"], ai["response_time_sum"], ai["max_latency"],
            ai["last_success_ts"], ai["last_failure_ts"]
        ))
    save_ai_usage(ai_rows)
    
    # Save Source Stats
    src_rows = []
    for src, st in metrics.source_stats.items():
        src_rows.append((
            metrics.run_id, metrics.daily["timestamp"], src, st["downloaded"], st["survived_regex"],
            st["survived_ontology"], st["survived_rules"], st["reached_ai"], st["alerts"],
            st["processing_time_sum"], st["processed_count"]
        ))
    save_source_stats(src_rows)
    
    # Save Workflow Health
    wh = {
        "run_id": metrics.run_id,
        "date": datetime.datetime.utcnow().strftime("%Y-%m-%d"),
        "timestamp": metrics.daily["timestamp"],
        "success": 1 if not metrics.exceptions else 0,
        "failed": 1 if metrics.exceptions else 0,
        "runtime": total_runtime,
        "articles": metrics.daily["articles_processed_count"],
        "emails": metrics.daily["emails_sent"],
        "git_commit": os.environ.get("GITHUB_SHA", "unknown"),
        "branch": os.environ.get("GITHUB_REF_NAME", "unknown"),
        "python_version": sys.version.split()[0],
        "exception": metrics.exceptions[-1]["exc_type"] if metrics.exceptions else ""
    }
    save_workflow_health(wh)
    
    # Save Exceptions
    for exc in metrics.exceptions:
        save_exception_log(metrics.run_id, exc["timestamp"], exc["exc_type"], exc["stack_trace"], exc["module"], exc["func_name"], exc["article_url"])
    
    # HTML Throttling Logic
    docs_path = "docs/index.html"
    generate_html = True
    if os.path.exists(docs_path) and not metrics.exceptions:
        mtime = os.path.getmtime(docs_path)
        age = time.time() - mtime
        if age < 3600: # 60 minutes
            generate_html = False
            
    if generate_html:
        print("[MONITORING] Generating HTML Dashboard (60m passed or exception occurred)...")
        logs = get_recent_lifecycle_logs()
        from src.html_generator import generate_dashboard_html
        metrics.calculate_health_score(total_runtime)
        generate_dashboard_html(logs, output_path=docs_path, metrics=metrics)
    else:
        print("[MONITORING] Skipping HTML Dashboard generation (throttle).")
        
    # Check if yesterday is synced to Google Sheets
    print("[MONITORING] Checking if yesterday's data needs syncing to Google Sheets...")
    from src.sheets import aggregate_and_sync_yesterday
    aggregate_and_sync_yesterday(SHEET_URL)
    
    print(f"[DAILY MEMORY] Session ended with {issuer_memory.size} issuers cached.")

    if source_stats:
        import datetime
        timestamp_str = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        update_last_checked(SHEET_URL, source_stats, timestamp_str)
        update_pipeline_metrics(SHEET_URL, funnel_metrics, timestamp_str)
        
    print("\\n[ONTOLOGY STATISTICS]")
    print(f"Total Foreign Articles Evaluated: {ontology_stats['total']}")
    if ontology_stats['total'] > 0:
        coverage = (ontology_stats['extracted'] / ontology_stats['total']) * 100
        print(f"Concepts Extracted: {ontology_stats['extracted']}")
        print(f"Missed Extractions: {ontology_stats['missed']}")
        print(f"Ontology Coverage:  {coverage:.1f}%")
        
if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        import traceback
        from src.monitoring import MetricsCollector
        metrics = MetricsCollector.get_instance()
        metrics.log_exception(type(e).__name__, traceback.format_exc(), "monitor", "main")
        print(f"[FATAL] Workflow crashed: {e}")
        # Need to still save the exception
        from src.database import save_exception_log, save_workflow_health
        import time, os, sys, datetime
        
        # Save Exceptions
        for exc in metrics.exceptions:
            save_exception_log(metrics.run_id, exc["timestamp"], exc["exc_type"], exc["stack_trace"], exc["module"], exc["func_name"], exc["article_url"])
            
        wh = {
            "run_id": metrics.run_id,
            "date": datetime.datetime.utcnow().strftime("%Y-%m-%d"),
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "success": 0,
            "failed": 1,
            "runtime": time.perf_counter() - metrics.workflow_start,
            "articles": metrics.daily.get("articles_processed_count", 0),
            "emails": metrics.daily.get("emails_sent", 0),
            "git_commit": os.environ.get("GITHUB_SHA", "unknown"),
            "branch": os.environ.get("GITHUB_REF_NAME", "unknown"),
            "python_version": sys.version.split()[0],
            "exception": type(e).__name__
        }
        save_workflow_health(wh)
        raise
"""

# Extract up to the start marker
if start_marker in content:
    pre = content.split(start_marker)[0]
    content = pre + new_end

with open('monitor.py', 'w') as f:
    f.write(content)
