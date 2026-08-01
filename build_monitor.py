import re
import shutil

shutil.copy2('monitor.py.bak', 'monitor.py')

with open('monitor.py', 'r') as f:
    content = f.read()

sig = "def _process_article(source_name, article_id, title, url, published, body, rules, playbook_map, global_exclusions=None, gold_standards=None, triage_all=False, funnel_metrics=None, issuer_memory=None, document_type=None, country=None, language=None, document_type_scores=None, ontology_stats=None, source_reliability_scores=None):"
new_sig = sig + """
    import time
    start_time = time.perf_counter()
    from src.monitoring import MetricsCollector
    metrics = MetricsCollector.get_instance()
    metrics.daily["downloaded"] += 1
    metrics.source_stats[source_name]["downloaded"] += 1
    
    ai_invoked = False
    stage_times = {}
    last_stage_time = start_time
    
    def mark_stage(stage_name):
        nonlocal last_stage_time
        now = time.perf_counter()
        stage_times[stage_name] = stage_times.get(stage_name, 0) + (now - last_stage_time)
        last_stage_time = now
        
    def conclude(ret_val, pipeline_stage, outcome, reason, issuer_name="Unknown", event_family="Unknown"):
        mark_stage(pipeline_stage)
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        slowest_stage = max(stage_times, key=stage_times.get) if stage_times else pipeline_stage
        metrics.log_article(article_id, source_name, url, title, country, language, document_type, issuer_name, event_family, pipeline_stage, outcome, reason, ai_invoked, elapsed_ms, slowest_stage)
        return ret_val
"""
content = content.replace(sig, new_sig)

content = content.replace(
    "if article_exists(article_key):\n        return 0",
    "mark_stage('Download')\n    if article_exists(article_key):\n        return conclude(0, 'Database', 'Skipped', 'Duplicate Article')"
)

content = content.replace(
    "if funnel_metrics: funnel_metrics[3] += 1\n        return 0",
    "if funnel_metrics: funnel_metrics[3] += 1\n        return conclude(0, 'Download', 'Rejected', 'Empty Body')"
)

content = content.replace(
    "return 1",
    "return conclude(1, 'Regex', 'Rejected', 'Duplicate Issuer', issuer)",
    1
)
content = content.replace(
    "return 1",
    "return conclude(1, 'Regex', 'Rejected', 'Global Exclusion', issuer)",
    1
)

content = content.replace(
    "if issuer == \"EXHAUSTED\":\n        print(\"    [CRITICAL] AI Providers are exhausted. Aborting ingestion loop to prevent spam and save cache.\")\n        return \"ABORT\"",
    "mark_stage('Regex')\n    if issuer == \"EXHAUSTED\":\n        print(\"    [CRITICAL] AI Providers are exhausted. Aborting ingestion loop to prevent spam and save cache.\")\n        return conclude(\"ABORT\", 'Issuer Extraction', 'Aborted', 'AI Exhausted')"
)

content = content.replace(
    "    article_obj = {",
    "    mark_stage('Ontology')\n    article_obj = {"
)

content = content.replace(
    "if matches:\n        if funnel_metrics:",
    "mark_stage('Rules')\n    if matches:\n        if funnel_metrics:"
)

content = content.replace(
    "ticker = extract_target_ticker(body)",
    "ai_invoked = True\n        ticker = extract_target_ticker(body)"
)
content = content.replace(
    "return \"ABORT\"",
    "return conclude(\"ABORT\", 'Rules', 'Aborted', 'AI Exhausted', issuer)",
    1
)
content = content.replace(
    "return 1",
    "return conclude(1, 'AI', 'Rejected', 'Private Company', ticker)",
    1
)
content = content.replace(
    "return \"ABORT\"",
    "return conclude(\"ABORT\", 'AI', 'Aborted', 'AI Exhausted', ticker, event_family)",
    1
)
content = content.replace(
    "return 1",
    "return conclude(1, 'AI', 'Rejected', 'False Positive', ticker, event_family)",
    1
)
content = content.replace(
    "return 1",
    "return conclude(1, 'AI', 'Archived', 'Unknown Event', ticker, event_family)",
    1
)
content = content.replace(
    "return 1",
    "return conclude(1, 'Rules', 'Rejected', 'No Options Available', ticker, event_family)",
    1
)
content = content.replace(
    "return 1",
    "return conclude(1, 'Playbook', 'Rejected', 'T12 Structural Floor Failed', ticker, event_family)",
    1
)
content = content.replace(
    "return 1",
    "return conclude(1, 'Database', 'Rejected', 'No Material Update', ticker, event_family)",
    1
)

content = content.replace(
    "    return 1\n",
    "    mark_stage('Email')\n    return conclude(1, 'Email', 'Alert Sent', 'Success', issuer, event_family)\n",
    1
)

content = content.replace("def main():", """def main():
    import traceback
    from src.monitoring import MetricsCollector
    from src.sheets import get_system_settings
    
    # Try fetching settings, fallback if Google API fails completely before pipeline starts
    try:
        from src.config.settings import SHEET_URL
        settings = get_system_settings(SHEET_URL)
    except Exception:
        settings = {}
        
    metrics = MetricsCollector.get_instance()
    metrics.set_settings(settings)
""")

end_script = """
    import time
    import sys
    import os
    import hashlib
    import datetime
    
    total_runtime = time.perf_counter() - metrics.workflow_start
    metrics.daily["total_runtime_s"] = total_runtime
    
    print("[MONITORING] Writing operational statistics to SQLite...")
    from src.database import save_lifecycle_logs, prune_lifecycle_logs, get_recent_lifecycle_logs, save_run_metrics, save_ai_usage, save_source_stats, save_workflow_health, save_exception_log, perform_housekeeping, get_dashboard_state, set_dashboard_state, get_30_day_average, get_30_day_source_averages
    
    log_rows = []
    for art_id, trace in metrics.article_traces.items():
        log_rows.append((
            art_id, trace["timestamp"], trace["source"], trace["title"], trace["url"], 
            trace["country"], trace["language"], trace["document_type"], trace["issuer"], 
            trace["event_family"], trace["pipeline_stage"], trace["outcome"], trace["reason"], trace["ai_invoked"], 
            trace["processing_time_ms"], trace["slowest_stage"]
        ))
    save_lifecycle_logs(log_rows)
    perform_housekeeping()
    
    metrics.daily["run_id"] = metrics.run_id
    metrics.daily["timestamp"] = datetime.datetime.utcnow().isoformat()
    save_run_metrics(metrics.daily)
    
    ai_rows = []
    for key_id, ai in metrics.ai_telemetry.items():
        ai_rows.append((
            metrics.run_id, metrics.daily["timestamp"], ai["provider"], ai["key_id"], ai["requests"],
            ai["success"], ai["failures"], ai["errors_429"], ai["errors_503"], ai["timeouts"],
            ai["retries"], ai["fallbacks"], ai["response_time_sum"], ai["max_latency"],
            ai["last_success_ts"], ai["last_failure_ts"]
        ))
    save_ai_usage(ai_rows)
    
    src_rows = []
    for src, st in metrics.source_stats.items():
        src_rows.append((
            metrics.run_id, metrics.daily["timestamp"], src, st["downloaded"], st["survived_regex"],
            st["survived_ontology"], st["survived_rules"], st["reached_ai"], st["alerts"],
            st["processing_time_sum"], st["processed_count"]
        ))
    save_source_stats(src_rows)
    
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
        "exception": metrics.exceptions[-1]["exc_type"] if metrics.exceptions else "",
        "workflow_version": "1.0",
        "run_number": os.environ.get("GITHUB_RUN_NUMBER", "1")
    }
    save_workflow_health(wh)
    
    for exc in metrics.exceptions:
        save_exception_log(metrics.run_id, exc["timestamp"], exc["exc_type"], exc["stack_trace"], exc["module"], exc["func_name"], exc["article_url"], exc["severity"])
        
    docs_path = "docs/index.html"
    last_publish = get_dashboard_state("last_publish")
    generate_html = False
    
    pub_interval = metrics.settings.get("Dashboard Publish Interval", 60) * 60
    
    if last_publish:
        age = time.time() - float(last_publish)
        if age > pub_interval:
            generate_html = True
    else:
        generate_html = True
        
    if metrics.exceptions or os.environ.get("FORCE_DASHBOARD") == "true":
        generate_html = True
        
    if generate_html:
        print("[MONITORING] Generating HTML Dashboard...")
        logs = get_recent_lifecycle_logs()
        metrics.calculate_health_score(total_runtime)
        from src.html_generator import generate_dashboard_html
        
        avg_30 = get_30_day_average()
        src_30 = get_30_day_source_averages()
        
        generate_dashboard_html(logs, output_path=docs_path, metrics=metrics, avg_30=avg_30, src_30=src_30)
        set_dashboard_state("last_publish", time.time())
    else:
        print("[MONITORING] Skipping HTML Dashboard generation (throttle).")
        
    print("[MONITORING] Checking if yesterday's data needs syncing to Google Sheets...")
    from src.sheets import aggregate_and_sync_yesterday
    aggregate_and_sync_yesterday(SHEET_URL)
    
    # Drift Alert Checks
    avg_30 = get_30_day_average()
    if avg_30:
        dl_thresh = metrics.settings.get("Download Drift Threshold", 20)
        alert_thresh = metrics.settings.get("Alert Drift Threshold", 50)
        ai_thresh = metrics.settings.get("AI Success Threshold", 80)
        
        avg_dl = avg_30.get("downloaded", 0)
        today_dl = metrics.daily.get("downloaded", 0)
        
        alerts = []
        if avg_dl > 50 and today_dl < (avg_dl * (1 - (dl_thresh/100.0))):
            alerts.append(f"CRITICAL: Downloads dropped by >{dl_thresh}% (Avg: {avg_dl:.0f}, Today: {today_dl})")
            
        avg_alerts = avg_30.get("emails_sent", 0)
        today_alerts = metrics.daily.get("emails_sent", 0)
        if avg_alerts > 1.0 and today_alerts == 0:
            alerts.append(f"CRITICAL: 0 Alerts generated today. Historical average is {avg_alerts:.1f}.")
            
        total_ai = metrics.daily.get("ai_calls", 0)
        if total_ai > 0:
            ai_succ = (metrics.daily.get("ai_successes", 0) / total_ai) * 100
            if ai_succ < ai_thresh:
                alerts.append(f"CRITICAL: AI Success Rate dropped to {ai_succ:.1f}% (Threshold: {ai_thresh}%)")
                
        if alerts:
            print("\\n".join(alerts))
            try:
                from src.alerts.email import send_email_alert
                from src.config.settings import ALERT_EMAIL_RECIPIENT
                if ALERT_EMAIL_RECIPIENT:
                    send_email_alert(
                        recipient=ALERT_EMAIL_RECIPIENT,
                        subject="[SSR CRITICAL] Pipeline Drift Alert",
                        body="The following critical anomalies were detected:\\n\\n" + "\\n".join(alerts)
                    )
            except Exception as e:
                print(f"Failed to send critical drift email: {e}")

    print(f"[DAILY MEMORY] Session ended with {issuer_memory.size} issuers cached.")
"""

# Replace from the end of memory flush
old_end = "    prune_daily_memory(SHEET_URL)"
content = content.replace(old_end, old_end + "\n" + end_script)

# Add try-except for main
if "if __name__ == '__main__':" in content:
    content = content.replace("if __name__ == '__main__':\n    main()", """if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        import traceback
        import datetime
        import os
        import sys
        import time
        from src.monitoring import MetricsCollector
        from src.database import save_exception_log, save_workflow_health
        metrics = MetricsCollector.get_instance()
        metrics.log_exception(type(e).__name__, traceback.format_exc(), "monitor", "main", severity="CRITICAL")
        print(f"[FATAL] Workflow crashed: {e}")
        
        for exc in metrics.exceptions:
            save_exception_log(metrics.run_id, exc["timestamp"], exc["exc_type"], exc["stack_trace"], exc["module"], exc["func_name"], exc["article_url"], exc["severity"])
            
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
            "exception": type(e).__name__,
            "workflow_version": "1.0",
            "run_number": os.environ.get("GITHUB_RUN_NUMBER", "1")
        }
        save_workflow_health(wh)
        
        try:
            from src.alerts.email import send_email_alert
            from src.config.settings import ALERT_EMAIL_RECIPIENT
            if ALERT_EMAIL_RECIPIENT:
                send_email_alert(
                    recipient=ALERT_EMAIL_RECIPIENT,
                    subject="[SSR CRITICAL] Workflow Crash",
                    body=f"Pipeline totally crashed:\\n\\n{traceback.format_exc()}"
                )
        except Exception:
            pass
        raise
""")

with open('monitor.py', 'w') as f:
    f.write(content)
