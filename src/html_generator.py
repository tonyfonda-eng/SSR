import json
import datetime
import os

def generate_dashboard_html(log_records, output_path="docs/index.html", metrics=None, avg_30=None, src_30=None):
    """
    Generates a static HTML dashboard organized into 5 logical sections.
    """
    
    # 1. Daily Report Card Stats
    health_score = 100
    total_runtime = 0
    total_dl = 0
    total_ai = 0
    total_alerts = 0
    total_exc = 0
    avoided_pct = 0.0
    status_text = "Healthy"
    status_color = "var(--success)"
    
    if metrics:
        total_runtime = metrics.daily.get("total_runtime_s", 0)
        health_score = metrics.calculate_health_score(total_runtime)
        total_dl = metrics.daily.get("downloaded", 0)
        total_ai = metrics.daily.get("ai_calls", 0)
        total_alerts = metrics.daily.get("emails_sent", 0)
        total_exc = len(metrics.exceptions)
        
        avoided = metrics.daily.get("rejected_before_regex", 0) + metrics.daily.get("rejected_by_regex", 0) + \
                  metrics.daily.get("rejected_by_exclusions", 0) + metrics.daily.get("rejected_by_ontology", 0) + \
                  metrics.daily.get("rejected_by_rules", 0)
        
        if total_dl > 0:
            avoided_pct = (avoided / total_dl) * 100
            
        if health_score < 80:
            status_text = "Warning"
            status_color = "var(--warning)"
        if health_score < 50 or total_exc > 0:
            status_text = "Critical"
            status_color = "var(--danger)"
            
        # Expected Alerts Logic
        avg_alerts = 0
        if avg_30:
            avg_alerts = avg_30.get("emails_sent", 0)
            if avg_alerts < 1.0 and total_alerts == 0:
                status_text = "Expected Low Alerts"
                status_color = "var(--gray)"
            elif avg_alerts > 1.0 and total_alerts == 0:
                status_text = "Unexpected 0 Alerts"
                status_color = "var(--danger)"
                
    rt_mins = int(total_runtime // 60)
    rt_secs = int(total_runtime % 60)

    # 2. Pipeline Funnel
    funnel_html = ""
    if metrics:
        f_steps = [
            ("Downloaded", total_dl),
            ("Rejected Pre-Regex", metrics.daily.get("rejected_before_regex", 0)),
            ("Rejected by Regex", metrics.daily.get("rejected_by_regex", 0)),
            ("Rejected by Exclusions", metrics.daily.get("rejected_by_exclusions", 0)),
            ("Rejected by Ontology", metrics.daily.get("rejected_by_ontology", 0)),
            ("Rejected by Rules", metrics.daily.get("rejected_by_rules", 0)),
            ("Reached AI", metrics.daily.get("reached_ai", 0)),
            ("Alerts Sent", total_alerts)
        ]
        for name, val in f_steps:
            pct = f"{(val/total_dl)*100:.1f}%" if total_dl > 0 else "0%"
            funnel_html += f"<tr><td>{name}</td><td>{val}</td><td>{pct}</td></tr>"

    # 3. AI Capacity
    ai_html = ""
    if metrics:
        # Simple estimates based on typical daily quotas
        g_usage = 0
        o_usage = 0
        for key_id, ai in metrics.ai_telemetry.items():
            if "gemini" in ai.get("provider", "").lower():
                g_usage += ai.get("requests", 0)
            else:
                o_usage += ai.get("requests", 0)
                
        # Approx 1500 per day for Google free tier (per key, if 7 keys = 10500)
        g_quota = 10500 
        o_quota = 5000 # Example
        
        g_rem = max(0, g_quota - g_usage)
        o_rem = max(0, o_quota - o_usage)
        
        ai_html += f"<tr><td>Google Gemini</td><td>{g_usage}</td><td>{(g_rem/g_quota)*100:.1f}%</td></tr>"
        ai_html += f"<tr><td>OpenRouter</td><td>{o_usage}</td><td>{(o_rem/o_quota)*100:.1f}%</td></tr>"

    # 4. Source Health
    source_html = ""
    if metrics and src_30:
        # Sort by Signal Rate
        sorted_sources = sorted(metrics.source_stats.items(), 
                              key=lambda x: (x[1]["alerts"] / x[1]["downloaded"]) if x[1]["downloaded"] > 0 else 0, 
                              reverse=True)
                              
        for src, st in sorted_sources:
            dl = st["downloaded"]
            alerts = st["alerts"]
            sig_rate = (alerts / dl) * 100 if dl > 0 else 0
            
            avg_dl = 0
            deg_warn = ""
            if src in src_30:
                avg_dl = src_30[src].get("avg_downloaded", 0)
                if avg_dl > 50 and dl < (avg_dl * 0.5):
                    deg_warn = f'<span style="color:var(--danger)">⚠ Degraded (Avg: {avg_dl:.0f})</span>'
            
            source_html += f"<tr><td>{src} {deg_warn}</td><td>{dl}</td><td>{alerts}</td><td>{sig_rate:.3f}%</td></tr>"

    # 5. Pathological & Recent Events
    sorted_logs = sorted(log_records, key=lambda x: x.get("processing_time_ms", 0), reverse=True)
    top_10 = sorted_logs[:10]
    top_10_html = ""
    for r in top_10:
        top_10_html += f"<tr><td>{r.get('source','')}</td><td>{r.get('title','')[:50]}...</td><td>{r.get('slowest_stage','Unknown')}</td><td style='color: var(--danger); font-weight: bold;'>{r.get('processing_time_ms',0)} ms</td></tr>"

    rows_html = ""
    for r in log_records:
        title = r.get("title", "")
        url = r.get("url", "")
        title_html = f'<a href="{url}" target="_blank">{title[:50]}...</a>' if url and title else title[:50]
        
        outcome = r.get("outcome", "")
        outcome_class = "status-archived"
        if "Alert" in outcome or "Success" in outcome: outcome_class = "status-alert"
        elif "Drop" in outcome or "Reject" in outcome or "Abort" in outcome: outcome_class = "status-drop"
        
        ai_inv = r.get("ai_invoked", 0)
        ai_badge = '<span class="badge status-drop">NO</span>' if not ai_inv else '<span class="badge status-alert">YES</span>'
        
        rows_html += "<tr>"
        rows_html += f'<td>{r.get("timestamp", "")}</td>'
        rows_html += f'<td>{r.get("source", "")}</td>'
        rows_html += f'<td>{title_html}</td>'
        rows_html += f'<td>{r.get("issuer", "")}</td>'
        rows_html += f'<td class="stage-cell">{r.get("pipeline_stage", "")}</td>'
        rows_html += f'<td><span class="badge {outcome_class}">{outcome}</span></td>'
        rows_html += f'<td>{r.get("reason", "")}</td>'
        rows_html += f'<td>{ai_badge}</td>'
        rows_html += f'<td>{r.get("processing_time_ms", 0)}</td>'
        rows_html += "</tr>\n"

    # 6. Dynamic Priority Queue
    from src.database import get_dashboard_state
    queue_json = get_dashboard_state("priority_queue", "[]")
    queue_data = json.loads(queue_json) if queue_json else []
    
    # Aggregate counts by source for the queue table
    queue_counts = {}
    for item in queue_data:
        src = item.get("source", "Unknown")
        pri = item.get("priority", 0.0)
        if src not in queue_counts:
            queue_counts[src] = {"count": 0, "priority": pri}
        queue_counts[src]["count"] += 1
        
    queue_html = ""
    for src, data in sorted(queue_counts.items(), key=lambda x: x[1]["priority"], reverse=True):
        p_val = data["priority"]
        badge_class = "status-alert" if p_val > 10 else ("status-archived" if p_val < 1 else "status-drop")
        queue_html += f"<tr><td>{src}</td><td>{data['count']}</td><td><span class='badge {badge_class}'>{p_val:.1f} (avg/hr)</span></td></tr>"

    if not queue_html:
        queue_html = "<tr><td colspan='3'>No priority data available for current window.</td></tr>"

    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SSR Operations Centre</title>
    <style>
        :root {{
            --bg-color: #0f172a;
            --panel-bg: #1e293b;
            --text-color: #f1f5f9;
            --border-color: #334155;
            --accent: #3b82f6;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --gray: #64748b;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            margin: 0;
            padding: 20px;
        }}
        .header-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }}
        h1 {{ font-size: 1.8rem; margin: 0; }}
        .subtitle {{ color: var(--gray); font-size: 0.9rem; margin-bottom: 20px; }}
        
        .report-card {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }}
        .metric-box {{
            background-color: var(--panel-bg);
            border: 1px solid var(--border-color);
            padding: 15px;
            border-radius: 8px;
            text-align: center;
        }}
        .metric-val {{
            font-size: 1.8rem;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        .metric-lbl {{
            font-size: 0.75rem;
            color: var(--gray);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        
        .grid-2 {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 30px;
        }}
        .panel {{
            background-color: var(--panel-bg);
            border-radius: 8px;
            border: 1px solid var(--border-color);
            padding: 15px;
        }}
        .panel-full {{ grid-column: 1 / -1; }}
        .panel h2 {{
            font-size: 1.1rem;
            margin-top: 0;
            margin-bottom: 15px;
            color: var(--gray);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        
        .table-container {{ overflow-x: auto; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.85rem;
            white-space: nowrap;
        }}
        th, td {{
            padding: 8px 12px;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
        }}
        th {{
            background-color: rgba(0,0,0,0.2);
            font-weight: 600;
            color: var(--gray);
        }}
        tr:hover td {{ background-color: rgba(255,255,255,0.02); }}
        a {{ color: var(--accent); text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        .badge {{
            padding: 3px 6px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
        }}
        .status-alert {{ background-color: rgba(16, 185, 129, 0.2); color: var(--success); }}
        .status-drop {{ background-color: rgba(239, 68, 68, 0.2); color: var(--danger); }}
        .status-archived {{ background-color: rgba(100, 116, 139, 0.2); color: var(--gray); }}
    </style>
</head>
<body>
    <div class="header-row">
        <div>
            <h1>SSR Operations Centre</h1>
            <div class="subtitle">Generated: {datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")}</div>
        </div>
    </div>
    
    <!-- 1. Daily Report Card -->
    <div class="report-card">
        <div class="metric-box">
            <div class="metric-val" style="color: {status_color}">{health_score}</div>
            <div class="metric-lbl">Health Score</div>
        </div>
        <div class="metric-box">
            <div class="metric-val">{total_dl:,}</div>
            <div class="metric-lbl">Articles</div>
        </div>
        <div class="metric-box">
            <div class="metric-val">{total_ai:,}</div>
            <div class="metric-lbl">AI Calls</div>
        </div>
        <div class="metric-box">
            <div class="metric-val">{avoided_pct:.2f}%</div>
            <div class="metric-lbl">Avoided AI %</div>
        </div>
        <div class="metric-box">
            <div class="metric-val">{total_alerts}</div>
            <div class="metric-lbl">Alerts</div>
        </div>
        <div class="metric-box">
            <div class="metric-val">{rt_mins}m {rt_secs}s</div>
            <div class="metric-lbl">Runtime</div>
        </div>
        <div class="metric-box">
            <div class="metric-val" style="color: {'var(--danger)' if total_exc > 0 else 'inherit'}">{total_exc}</div>
            <div class="metric-lbl">Exceptions</div>
        </div>
        <div class="metric-box">
            <div class="metric-val" style="color: {status_color}; font-size: 1.2rem; display: flex; align-items: center; justify-content: center; height: 100%;">{status_text}</div>
            <div class="metric-lbl">Status</div>
        </div>
    </div>
    
    <div class="grid-2">
        <!-- 2. Pipeline Funnel -->
        <div class="panel">
            <h2>Pipeline Funnel</h2>
            <div class="table-container">
                <table>
                    <thead><tr><th>Stage</th><th>Count</th><th>% of Total</th></tr></thead>
                    <tbody>{funnel_html}</tbody>
                </table>
            </div>
        </div>
        
        <!-- 3. AI Capacity -->
        <div class="panel">
            <h2>AI Capacity Forecast</h2>
            <div class="table-container">
                <table>
                    <thead><tr><th>Provider</th><th>Usage Today</th><th>Est. Remaining</th></tr></thead>
                    <tbody>{ai_html}</tbody>
                </table>
            </div>
        </div>
        
        <!-- 4. Source Health -->
        <div class="panel panel-full">
            <h2>Source Health & Signal Rates</h2>
            <div class="table-container">
                <table>
                    <thead><tr><th>Source</th><th>Downloaded</th><th>Alerts</th><th>Signal Rate</th></tr></thead>
                    <tbody>{source_html}</tbody>
                </table>
            </div>
        </div>
        
        <!-- Priority Queue Heatmap -->
        <div class="panel panel-full">
            <h2>Dynamic Priority Allocation (Current Hour Peak)</h2>
            <div class="table-container">
                <table>
                    <thead><tr><th>Source</th><th>Articles Allocated (Max 50)</th><th>Priority Score (Avg Historical Vol)</th></tr></thead>
                    <tbody>{queue_html}</tbody>
                </table>
            </div>
        </div>
        
        <!-- 5. Pathological Cases -->
        <div class="panel panel-full">
            <h2>Pathological Cases (Top 10 Slowest Articles)</h2>
            <div class="table-container">
                <table>
                    <thead><tr><th>Source</th><th>Headline</th><th>Slowest Stage</th><th>Total Time</th></tr></thead>
                    <tbody>{top_10_html}</tbody>
                </table>
            </div>
        </div>
        
        <!-- Execution Log -->
        <div class="panel panel-full">
            <h2>Pipeline Execution Log (Rolling 14-Day)</h2>
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Timestamp</th><th>Source</th><th>Headline</th><th>Issuer</th>
                            <th>Pipeline Stage</th><th>Outcome</th><th>Reason</th><th>AI Invoked</th><th>Time (ms)</th>
                        </tr>
                    </thead>
                    <tbody>{rows_html}</tbody>
                </table>
            </div>
        </div>
    </div>
</body>
</html>"""

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_template)
        
    print(f"[MONITORING] Dashboard generated at {output_path} with {len(log_records)} records.")
