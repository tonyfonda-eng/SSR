import os
import json
import csv
import datetime
import statistics
from src.audit.queries import (
    get_daily_run_summary,
    get_daily_stage_funnel,
    get_rejections_by_stage,
    get_top_rejected_articles,
    get_source_coverage,
    get_historical_source_averages,
    get_db_integrity,
    get_alerts_generated,
    get_config_changelog,
    get_raw_appendix,
    get_audit_source_metrics,
    get_audit_ai_metrics,
    get_audit_events,
    get_lifetime_source_reliability,
    get_ai_drift_metrics,
    get_db_connection,
    RESEARCH_DB
)
from src.providers.router import ProviderRouter

def calculate_anomaly(raw, avg):
    if avg == 0:
        return 0
    return ((raw - avg) / avg) * 100

def get_traffic_light(deviation_pct):
    if abs(deviation_pct) < 15:
        return "🟢"
    elif abs(deviation_pct) <= 30:
        return "🟡"
    return "🔴"

def get_scraper_grade(dev_pct, emergency_stop):
    if emergency_stop:
        return "F"
    ad = abs(dev_pct)
    if ad < 5: return "A+"
    elif ad < 10: return "A"
    elif ad < 20: return "B"
    elif ad < 30: return "C"
    elif ad < 40: return "D"
    return "F"

def append_to_csv(filepath, metrics_row):
    file_exists = os.path.isfile(filepath)
    with open(filepath, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(metrics_row.keys()))
        if not file_exists:
            writer.writeheader()
        writer.writerow(metrics_row)

def get_average_ontology_score(date_str):
    conn = get_db_connection(RESEARCH_DB)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ontology_metadata FROM evaluation_ledger 
        WHERE date(runtime_timestamp) = ? 
        AND terminal_stage != 'dedupe_hash'
    """, (date_str,))
    rows = cursor.fetchall()
    conn.close()
    
    scores = []
    for r in rows:
        try:
            meta = json.loads(r['ontology_metadata'])
            if 'score' in meta:
                scores.append(float(meta['score']))
        except:
            pass
    return sum(scores) / len(scores) if scores else 0.0

def generate_markdown_report(date_str):
    runs = get_daily_run_summary(date_str)
    funnel = get_daily_stage_funnel(date_str)
    top_rejected = get_top_rejected_articles(date_str, limit=50)
    source_coverage = get_source_coverage(date_str)
    alerts = get_alerts_generated(date_str)
    hist_30d = get_historical_source_averages(date_str, days=30)
    db_issues = get_db_integrity()
    audit_sources = get_audit_source_metrics(date_str)
    audit_ai = get_audit_ai_metrics(date_str)
    audit_events = get_audit_events(date_str)
    lifetime_rel = get_lifetime_source_reliability()
    ai_drift = get_ai_drift_metrics(date_str)
    appendix = get_raw_appendix(date_str)
    
    run_ids = [r['run_id'] for r in runs]
    total_runs = len(runs)
    total_scanned = sum(r['total_scanned'] for r in runs)
    total_unique = sum(s['unique_articles'] for s in source_coverage)
    total_errors = sum(r['errors'] for r in runs)
    total_alerts = len(alerts)
    avg_runtime = sum(r['runtime'] for r in runs) / total_runs if total_runs else 0
    
    # Versioning
    latest_run = runs[-1] if runs else {}
    git_commit = latest_run.get('git_commit', 'Unknown')
    git_branch = latest_run.get('branch', 'Unknown')
    today_config, yest_config = get_config_changelog(date_str)
    cfg_hash = "CFG-" + str(hash(json.dumps(today_config)))[:12].replace("-", "") if today_config else "Unknown"
    ont_version = len(today_config.get("semantic_concepts", []))
    rule_version = len(today_config.get("rules", []))
    playbook_version = len(today_config.get("playbooks", []))
    
    # Audit Source Mapping
    audit_source_map = {s['source']: s for s in audit_sources}
    
    # Could SSR have missed something today?
    missed_sections = []
    emergency_stops = 0
    total_avg_30d = 0
    sources_analyzed = []
    
    csv_source_stats = {}
    
    for s in source_coverage:
        name = s['source']
        raw = s['total_articles']
        avg = hist_30d.get(name, 0)
        total_avg_30d += avg
        dev_pct = calculate_anomaly(raw, avg)
        
        audit_meta = audit_source_map.get(name, {})
        emergency_stop = bool(audit_meta.get('emergency_stop'))
        reason = str(audit_meta.get('reasons', '') or '')
        
        if emergency_stop:
            emergency_stops += 1
            missed_sections.append(f"**{name}**: 🔴 EMERGENCY STOP ACTIVATED. Reason: {reason}. Expected ~{avg:.0f} articles, got {raw}. Acquisition failure is HIGH.")
        elif dev_pct < -30:
            missed_sections.append(f"**{name}**: 🟡 Severe volume drop ({dev_pct:.1f}%). Expected ~{avg:.0f}, got {raw}. Potential acquisition gap.")
            
        grade = get_scraper_grade(dev_pct, emergency_stop)
        light = get_traffic_light(dev_pct) if not emergency_stop else "🔴"
        
        sources_analyzed.append({
            "name": name, "mode": s['ingestion_mode'], "raw": raw, "unique": s['unique_articles'],
            "avg": avg, "dev_pct": dev_pct, "grade": grade, "light": light, "emergency_stop": emergency_stop,
            "reason": reason
        })
        csv_source_stats[name] = raw
        
    if not missed_sections:
        missed_sections.append("✅ No emergency stops or severe volume drops detected. Pipeline acquisition appears complete.")

    # Mathematical Health & Confidence
    global_dev = calculate_anomaly(total_scanned, total_avg_30d) if total_avg_30d else 0
    acq_health = max(0, 100 - abs(global_dev) - (emergency_stops * 15))
    
    pipe_error_rate = (total_errors / total_scanned) if total_scanned else 0
    pipe_health = max(0, 100 - (pipe_error_rate * 500))
    
    db_health = max(0, 100 - (len(db_issues) * 20))
    cov_health = max(0, 100 - (emergency_stops * 25))
    
    # Estimated Recall (Different from Confidence)
    estimated_recall = max(0.0, 100 - (emergency_stops * 10) - (abs(global_dev) / 2) - (pipe_error_rate * 100))
    recall_reasons = []
    if emergency_stops == 0 and abs(global_dev) < 10 and pipe_error_rate == 0:
        recall_reasons = ["No emergency limits", "No scraper failures", f"Historical acquisition within {abs(global_dev):.1f}%"]
    else:
        if emergency_stops > 0: recall_reasons.append(f"{emergency_stops} sources hit emergency limits")
        if abs(global_dev) >= 10: recall_reasons.append(f"Historical acquisition deviated by {abs(global_dev):.1f}%")
        if pipe_error_rate > 0: recall_reasons.append(f"Pipeline error rate {pipe_error_rate*100:.1f}%")
    
    # AI Metrics
    ai_total_calls = 0
    ai_total_cost = 0.0
    ai_failures = 0
    ai_successes = 0
    ai_avg_latency = 0.0
    
    if audit_ai:
        ai_total_calls = sum(a['successes'] + a['failures'] for a in audit_ai)
        ai_total_cost = sum(a['total_cost'] for a in audit_ai)
        ai_failures = sum(a['failures'] for a in audit_ai)
        ai_successes = sum(a['successes'] for a in audit_ai)
        ai_avg_latency = sum(a['avg_latency'] for a in audit_ai) / len(audit_ai)
        
    ai_health = max(0, 100 - ((ai_failures / ai_total_calls * 1000) if ai_total_calls else 0)) if ai_total_calls else 100
    if ai_total_calls == 0 and total_scanned > 0: ai_health = 0
    
    # Coverage Score × Pipeline Score × Integrity Score × Source Availability
    confidence = (acq_health/100) * (pipe_health/100) * (db_health/100) * (cov_health/100) * 100

    # False Negatives sorting by completeness
    fn_list = []
    for r in top_rejected:
        score = 0.0
        try:
            if r['ontology_metadata']:
                om = json.loads(r['ontology_metadata'])
                score = float(om.get('score', 0.0))
        except:
            pass
        fn_list.append((score, r))
    fn_list.sort(key=lambda x: x[0], reverse=True)
    
    # Behavioural Change Log
    yest = (datetime.datetime.strptime(date_str, "%Y-%m-%d") - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    today_ont = get_average_ontology_score(date_str)
    yest_ont = get_average_ontology_score(yest)
    ont_diff = today_ont - yest_ont

    # 3. Massive CSV Logging
    metrics_row = {
        "Date": date_str,
        "Total_Runs": total_runs,
        "Raw_Scanned": total_scanned,
        "Unique_Articles": total_unique,
        "Alerts_Dispatched": total_alerts,
        "Confidence_Score": round(confidence, 1),
        "Acquisition_Health": round(acq_health, 1),
        "Pipeline_Health": round(pipe_health, 1),
        "AI_Health": round(ai_health, 1),
        "DB_Integrity_Health": round(db_health, 1),
        "AI_Total_Calls": ai_total_calls,
        "AI_Failures": ai_failures,
        "AI_Avg_Latency_ms": round(ai_avg_latency, 1),
        "AI_Total_Cost": round(ai_total_cost, 4),
        "Average_Ontology_Score": round(today_ont, 2),
        "Ontology_Delta": round(ont_diff, 2),
        "Emergency_Stops": emergency_stops,
        "Total_Errors": total_errors,
        "Avg_Runtime_s": round(avg_runtime, 1),
    }
    
    # Add explicit sources
    for src in ["Business Wire", "PR Newswire", "GlobeNewswire", "SEC EDGAR"]:
        metrics_row[src.replace(" ", "_")] = csv_source_stats.get(src, 0)
        
    os.makedirs("docs", exist_ok=True)
    append_to_csv("docs/daily_metrics.csv", metrics_row)

    # 4. CTO Synthesis
    ai_recommendations = "_AI interpretation bypassed: GEMINI_API_KEY not configured._"
    if os.environ.get("GEMINI_API_KEY"):
        try:
            router = ProviderRouter()
            prompt = (
                "You are the CTO of Special Situations Radar. I am providing you with today's deterministic flight recorder metrics.\n"
                "Do NOT simply list the numbers back to me.\n"
                "Your job is to analyze these anomalies, health scores, and operational risks, and provide 3-5 concrete operational recommendations.\n\n"
                f"Confidence Score: {confidence:.1f}%\n"
                f"Health Scores: ACQ={acq_health:.1f}, PIPE={pipe_health:.1f}, AI={ai_health:.1f}, DB={db_health:.1f}\n"
                f"Emergency Stops: {emergency_stops}\n"
                f"Top Risks:\n" + "\n".join(missed_sections) + "\n\n"
                "Provide your response as a concise Markdown block with actionable technical recommendations."
            )
            response = router.generate(prompt)
            if response: ai_recommendations = response
        except Exception as e:
            ai_recommendations = f"_AI Synthesis Failed: {e}_"

    # 5. Build Markdown
    md = []
    md.append(f"# SSR Institutional Flight Recorder — {date_str}")
    md.append(f"## System Confidence: {confidence:.1f}%")
    md.append("*Calculation: (Acquisition Health × Pipeline Health × Integrity Score × Source Availability)*")
    md.append("")
    
    md.append("## 1. Could SSR have missed something today?")
    for ms in missed_sections:
        md.append(f"- {ms}")
    md.append("")
    
    md.append("## 2. Institutional KPI Dashboard")
    md.append("| KPI | Metric | Context |")
    md.append("|---|---|---|")
    md.append(f"| **Acquisition** | {total_scanned} Raw, {total_unique} Unique | vs {total_avg_30d:.0f} 30d Avg |")
    md.append(f"| **Estimated Recall** | {estimated_recall:.1f}% | {', '.join(recall_reasons)} |")
    md.append(f"| **Alerts Generated** | {total_alerts} | Total Dispatched |")
    md.append(f"| **AI Utilisation** | {ai_total_calls} Calls | Cost: ${ai_total_cost:.3f} |")
    md.append(f"| **False Negatives** | {len(top_rejected)} Late Drops | Requires Tuning |")
    md.append(f"| **System Latency** | {avg_runtime:.1f}s / run | Across {total_runs} runs |")
    md.append("")
    
    md.append("## 3. Version Manifest")
    md.append(f"- **Git Commit**: `{git_commit}`")
    md.append(f"- **Git Branch**: `{git_branch}`")
    md.append(f"- **Config Hash**: `{cfg_hash}`")
    md.append(f"- **Ontology Version**: `{ont_version}` concepts")
    md.append(f"- **Rule Version**: `{rule_version}` rules")
    md.append(f"- **Playbook Version**: `{playbook_version}` playbooks")
    md.append("")

    md.append("## 3. Behavioural Change Log")
    md.append(f"- **Average Ontology Score:** {today_ont:.2f}")
    if ont_diff > 0.05:
        md.append(f"- **Shift:** 📈 Up {ont_diff:+.2f} vs yesterday. Likely richer M&A news mix.")
    elif ont_diff < -0.05:
        md.append(f"- **Shift:** 📉 Down {ont_diff:+.2f} vs yesterday. Likely higher noise ratio.")
    else:
        md.append(f"- **Shift:** ➡️ Flat ({ont_diff:+.2f}). Stable news mix.")
    md.append("")
    
    md.append("## 5. Source Acquisition & Scraper Health")
    md.append("| Source | Mode | Grade | Status | Raw | 30d Avg | Dev % | Lifetime Rel | Emergency Stop |")
    md.append("|---|---|---|---|---|---|---|---|---|")
    for s in sources_analyzed:
        em_str = f"⚠️ YES ({s['reason']})" if s['emergency_stop'] else "No"
        rel_str = f"{lifetime_rel.get(s['name'], 100.0):.1f}%"
        md.append(f"| {s['name']} | {s['mode']} | **{s['grade']}** | {s['light']} | {s['raw']} | {s['avg']:.0f} | {s['dev_pct']:+.1f}% | {rel_str} | {em_str} |")
    md.append("")
    
    md.append("## 6. AI Prompt Economics, Telemetry & Drift")
    if audit_ai:
        md.append("### Telemetry")
        md.append("| Provider | Prompt Type | Calls | Latency | Tokens In | Tokens Out | Cost | Failures |")
        md.append("|---|---|---|---|---|---|---|---|")
        for a in audit_ai:
            md.append(f"| {a['provider']} | {a['prompt_type']} | {a['successes']} | {a['avg_latency']:.0f}ms | {a['input_tokens']} | {a['output_tokens']} | ${a['total_cost']:.4f} | {a['failures']} |")
            
        md.append("\n### Drift Metrics")
        for days in [7, 30, 90]:
            md.append(f"- **{days}d Avg Tokens**: {ai_drift.get(f'{days}d_tokens', 0):.0f}")
    else:
        md.append("No AI telemetry recorded.")
    md.append("")
    
    md.append("## 7. Black-Box Audit Events")
    if audit_events:
        md.append("| Timestamp | Source/Provider | Event | Severity | Details |")
        md.append("|---|---|---|---|---|")
        for e in audit_events:
            md.append(f"| {e['timestamp'][11:16]} | {e['source_or_provider']} | {e['event_type']} | {e['severity']} | {e['details']} |")
    else:
        md.append("No critical events recorded.")
    md.append("")
    
    md.append("## 8. Pipeline Funnel Analytics")
    md.append("| Stage | Entered | Passed | Rejected | Pass % | Avg Latency (ms) |")
    md.append("|---|---|---|---|---|---|")
    stage_order = ['dedupe_hash', 'dedupe_issuer_memory', 'ontology_concepts', 'regex_rules', 
                   'python_issuer_extraction', 'python_ticker_lookup', 'ai_ticker_resolution',
                   'entity_confidence_gate', 'financial_market_cap', 'ai_event_classification', 
                   'playbook_eligibility_check']
    for stage in stage_order:
        if stage in funnel:
            m = funnel[stage]
            entered = m['entered']
            passed = m['passed']
            rejected = m['rejected']
            pass_pct = (passed / entered * 100) if entered else 0
            avg_latency = (m['cpu_ms'] + m['network_ms']) / entered if entered else 0
            md.append(f"| {stage} | {entered} | {passed} | {rejected} | {pass_pct:.1f}% | {avg_latency:.2f} |")
    md.append("")
    
    md.append("## 9. Today's Biggest Misses (False Negatives)")
    if fn_list:
        md.append("Sorted by `evidence_completeness_score`. High scores that dropped late require rules tuning.")
        md.append("| Score | Stage | Drop Reason | Headline |")
        md.append("|---|---|---|---|")
        for score, r in fn_list[:25]:
            md.append(f"| {score:.2f} | {r['final_stage']} | {r['drop_reason']} | {r['headline']} |")
    else:
        md.append("No late-stage misses today.")
    md.append("")
    
    md.append("## 10. SQL Database Integrity")
    if db_issues:
        for iss in db_issues:
            md.append(f"- 🔴 {iss}")
    else:
        md.append("- 🟢 100% Integrity Checks Passed")
    md.append("")

    md.append("## 11. CTO Recommendations (AI Synthesis)")
    md.append(ai_recommendations)
    md.append("")
    
    md.append("## 12. Replay Log")
    md.append(f"Executed {total_runs} total runs today. Run IDs:")
    md.append("```text")
    for r in run_ids:
        md.append(r)
    md.append("```")
    md.append("")
    
    md.append("## 13. Appendix: Raw SQL Dump")
    md.append("### `workflow_health` (Top 3)")
    md.append("```json\n" + json.dumps(appendix.get('workflow_health', [])[:3], indent=2) + "\n```")

    return "\n".join(md)

def run_daily_audit():
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    print(f"Generating Institutional Flight Recorder V4 for {today}...")
    
    markdown_content = generate_markdown_report(today)
    
    output_dir = "docs/daily_audit"
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, f"{today}.md")
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(markdown_content)
        
    print(f"Report written to {filepath}")
    return filepath

if __name__ == "__main__":
    run_daily_audit()
