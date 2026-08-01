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
    
    queue_html = ""
    for item in queue_data:
        src = item.get("source", "Unknown")
        quota = item.get("quota", 0)
        backlog = item.get("backlog", 0)
        p_val = item.get("priority", 0.0)
        
        badge_class = "status-alert" if p_val > 10 else ("status-archived" if p_val < 1 else "status-drop")
        queue_html += f"<tr><td>{src}</td><td>{quota} / {backlog}</td><td><span class='badge {badge_class}'>{p_val:.2f}</span></td></tr>"

    if not queue_html:
        queue_html = "<tr><td colspan='3'>No priority data available for current window.</td></tr>"

    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SSR Operations Centre</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-gradient: radial-gradient(circle at 10% 20%, rgb(14, 20, 31) 0%, rgb(8, 11, 17) 90%);
            --panel-bg: rgba(23, 32, 51, 0.6);
            --panel-border: rgba(255, 255, 255, 0.08);
            --panel-hover-bg: rgba(30, 41, 59, 0.8);
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --accent: #38bdf8;
            --accent-glow: rgba(56, 189, 248, 0.4);
            --success: #10b981;
            --success-glow: rgba(16, 185, 129, 0.2);
            --warning: #f59e0b;
            --danger: #ef4444;
            --danger-glow: rgba(239, 68, 68, 0.2);
        }}

        body {{
            font-family: 'Inter', sans-serif;
            background: var(--bg-gradient);
            color: var(--text-main);
            margin: 0;
            padding: 30px;
            min-height: 100vh;
            background-attachment: fixed;
        }}

        /* Typography */
        h1, h2, h3 {{
            font-family: 'Outfit', sans-serif;
            margin: 0;
        }}
        h1 {{
            font-size: 2.2rem;
            font-weight: 700;
            background: linear-gradient(90deg, #f8fafc, #94a3b8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: -0.02em;
        }}
        .header-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--panel-border);
        }}
        .subtitle {{
            color: var(--text-muted);
            font-size: 0.95rem;
            margin-top: 5px;
            font-weight: 500;
        }}

        /* Glassmorphic Panels */
        .panel, .metric-box {{
            background: var(--panel-bg);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid var(--panel-border);
            border-radius: 16px;
            box-shadow: 0 4px 24px -1px rgba(0, 0, 0, 0.3);
            transition: transform 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
        }}
        .metric-box {{
            padding: 20px;
            text-align: center;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
        }}
        .metric-box:hover {{
            transform: translateY(-4px);
            box-shadow: 0 10px 30px -5px rgba(0, 0, 0, 0.4);
            background: var(--panel-hover-bg);
        }}
        .metric-val {{
            font-family: 'Outfit', sans-serif;
            font-size: 2.2rem;
            font-weight: 800;
            margin-bottom: 8px;
            color: var(--text-main);
        }}
        .metric-lbl {{
            font-size: 0.8rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-weight: 600;
        }}

        /* Layouts */
        .report-card {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        .grid-2 {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 25px;
            margin-bottom: 30px;
        }}
        .panel {{
            padding: 24px;
        }}
        .panel-full {{
            grid-column: 1 / -1;
        }}
        .panel h2 {{
            font-size: 1.25rem;
            margin-bottom: 20px;
            color: var(--text-main);
            letter-spacing: 0.02em;
            display: flex;
            align-items: center;
        }}
        .panel h2::before {{
            content: '';
            display: inline-block;
            width: 8px;
            height: 8px;
            background: var(--accent);
            border-radius: 50%;
            margin-right: 12px;
            box-shadow: 0 0 10px var(--accent-glow);
        }}

        /* Tables & Lists */
        .table-container {{
            overflow-x: auto;
            border-radius: 8px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
            white-space: nowrap;
        }}
        th, td {{
            padding: 12px 16px;
            text-align: left;
            border-bottom: 1px solid rgba(255, 255, 255, 0.04);
        }}
        th {{
            font-family: 'Outfit', sans-serif;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            font-size: 0.75rem;
            letter-spacing: 0.05em;
            cursor: pointer;
            transition: color 0.2s ease;
        }}
        th:hover {{
            color: var(--text-main);
        }}
        tr {{
            transition: background 0.2s ease;
        }}
        tbody tr:hover {{
            background: rgba(255, 255, 255, 0.03);
        }}
        
        /* Links and Badges */
        a {{
            color: var(--accent);
            text-decoration: none;
            transition: color 0.2s ease, text-shadow 0.2s ease;
        }}
        a:hover {{
            color: #7dd3fc;
            text-shadow: 0 0 8px var(--accent-glow);
        }}
        .badge {{
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 0.75rem;
            font-weight: 600;
            font-family: 'Outfit', sans-serif;
            display: inline-block;
            letter-spacing: 0.02em;
            border: 1px solid transparent;
        }}
        .status-alert {{
            background-color: var(--success-glow);
            color: #34d399;
            border-color: rgba(52, 211, 153, 0.2);
        }}
        .status-drop {{
            background-color: var(--danger-glow);
            color: #f87171;
            border-color: rgba(248, 113, 113, 0.2);
        }}
        .status-archived {{
            background-color: rgba(148, 163, 184, 0.15);
            color: #cbd5e1;
            border-color: rgba(203, 213, 225, 0.15);
        }}
        .stage-cell {{
            color: var(--text-muted);
            font-family: monospace;
            font-size: 0.85rem;
        }}

        /* Scrollbar styling */
        ::-webkit-scrollbar {{
            width: 8px;
            height: 8px;
        }}
        ::-webkit-scrollbar-track {{
            background: rgba(0, 0, 0, 0.2);
            border-radius: 4px;
        }}
        ::-webkit-scrollbar-thumb {{
            background: rgba(255, 255, 255, 0.1);
            border-radius: 4px;
        }}
        ::-webkit-scrollbar-thumb:hover {{
            background: rgba(255, 255, 255, 0.2);
        }}
    </style>
</head>
<body>
    <div class="header-row">
        <div>
            <h1>SSR Operations Centre</h1>
            <div class="subtitle">Generated: {datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")}</div>
        </div>
        <div>
            <a href="archive.html" style="background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); color: white; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-weight: 600; font-family: 'Outfit', sans-serif; transition: all 0.2s;">
                📂 Database Archive
            </a>
        </div>
    </div>
    
    <!-- 1. Daily Report Card -->
    <div class="report-card">
        <div class="metric-box">
            <div class="metric-val" style="color: {status_color}; text-shadow: 0 0 15px {status_color}40;">{health_score}</div>
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
            <div class="metric-val" style="color: var(--accent); text-shadow: 0 0 15px var(--accent-glow);">{total_alerts}</div>
            <div class="metric-lbl">Alerts Generated</div>
        </div>
        <div class="metric-box">
            <div class="metric-val">{rt_mins}m {rt_secs}s</div>
            <div class="metric-lbl">Pipeline Runtime</div>
        </div>
        <div class="metric-box">
            <div class="metric-val" style="color: {'var(--danger)' if total_exc > 0 else 'inherit'}">{total_exc}</div>
            <div class="metric-lbl">Exceptions</div>
        </div>
        <div class="metric-box" style="background: rgba(255,255,255,0.03);">
            <div class="metric-val" style="color: {status_color}; font-size: 1.4rem; height: 100%; display: flex; align-items: center; justify-content: center;">{status_text}</div>
            <div class="metric-lbl">System Status</div>
        </div>
    </div>
    
    <div class="grid-2">
        <!-- 2. Pipeline Funnel -->
        <div class="panel">
            <h2>Pipeline Funnel</h2>
            <div class="table-container">
                <table class="sortable">
                    <thead><tr><th>Stage</th><th>Count</th><th>% of Total</th></tr></thead>
                    <tbody>{funnel_html}</tbody>
                </table>
            </div>
        </div>
        
        <!-- 3. AI Capacity -->
        <div class="panel">
            <h2>AI Capacity Forecast</h2>
            <div class="table-container">
                <table class="sortable">
                    <thead><tr><th>Provider</th><th>Usage Today</th><th>Est. Remaining</th></tr></thead>
                    <tbody>{ai_html}</tbody>
                </table>
            </div>
        </div>
        
        <!-- 4. Source Health -->
        <div class="panel panel-full">
            <h2>Source Health & Signal Rates</h2>
            <div class="table-container">
                <table class="sortable">
                    <thead><tr><th>Source</th><th>Downloaded</th><th>Alerts</th><th>Signal Rate</th></tr></thead>
                    <tbody>{source_html}</tbody>
                </table>
            </div>
        </div>
        
        <!-- Priority Queue Heatmap -->
        <div class="panel panel-full">
            <h2>Dynamic Priority Allocation (Current Hour Peak)</h2>
            <div class="table-container">
                <table class="sortable">
                    <thead><tr><th>Source</th><th>Quota Allocated / Backlog</th><th>Priority Weight (EMA)</th></tr></thead>
                    <tbody>{queue_html}</tbody>
                </table>
            </div>
        </div>
        
        <!-- 5. Pathological Cases -->
        <div class="panel panel-full">
            <h2>Pathological Cases (Top 10 Slowest Articles)</h2>
            <div class="table-container">
                <table class="sortable">
                    <thead><tr><th>Source</th><th>Headline</th><th>Slowest Stage</th><th>Total Time</th></tr></thead>
                    <tbody>{top_10_html}</tbody>
                </table>
            </div>
        </div>
        
        <!-- Execution Log -->
        <div class="panel panel-full">
            <h2>Pipeline Execution Log (Rolling 14-Day)</h2>
            <div class="table-container" style="max-height: 500px;">
                <table class="sortable">
                    <thead style="position: sticky; top: 0; background: rgba(23, 32, 51, 0.95); z-index: 10;">
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
    
    <script>
        // Simple Vanilla JS Table Sorter
        document.addEventListener('DOMContentLoaded', () => {{
            const getCellValue = (tr, idx) => tr.children[idx].innerText || tr.children[idx].textContent;
            
            const comparer = (idx, asc) => (a, b) => ((v1, v2) => 
                v1 !== '' && v2 !== '' && !isNaN(v1) && !isNaN(v2) ? v1 - v2 : v1.toString().localeCompare(v2)
                )(getCellValue(asc ? a : b, idx), getCellValue(asc ? b : a, idx));
                
            document.querySelectorAll('th').forEach(th => th.addEventListener('click', (() => {{
                const table = th.closest('table');
                const tbody = table.querySelector('tbody');
                Array.from(tbody.querySelectorAll('tr'))
                    .sort(comparer(Array.from(th.parentNode.children).indexOf(th), this.asc = !this.asc))
                    .forEach(tr => tbody.appendChild(tr));
            }})));
        }});
    </script>
</body>
</html>"""

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_template)
        
    print(f"[MONITORING] Dashboard generated at {output_path} with {len(log_records)} records.")
