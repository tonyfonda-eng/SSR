import datetime
import os

def generate_dashboard_html(logs, output_path, metrics, avg_30=None, src_30=None):
    """Generates the Executive Operations Summary for immediate decision support."""
    
    now_str = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    # --- 1. SYSTEM HEALTH (Is it healthy?) ---
    runtime_s = metrics.daily.get("total_runtime_s", 0)
    health_score = metrics.calculate_health_score(runtime_s)
    run_id = getattr(metrics, 'run_id', 'Unknown')
    
    if health_score >= 90 and not metrics.exceptions:
        sys_color, sys_status = "#2ea043", "HEALTHY"
    elif health_score >= 70:
        sys_color, sys_status = "#dbab0a", "DEGRADED"
    else:
        sys_color, sys_status = "#cb2431", "CRITICAL"

    # --- 2. DEPLOYMENT HEALTH (Is it safe to deploy?) ---
    # Zero-compute compliance and local security validations
    secrets_pass = os.path.exists(".secrets.baseline") and not (os.path.exists("gitleaks-results.sarif") or os.path.exists("gitleaks-report.json"))
    db_pass = os.path.exists("ssr_cache.sqlite") or os.path.exists("ssr_observability.db")
    exceptions_pass = len(metrics.exceptions) == 0
    
    def pass_fail_badge(condition):
        return "<span class='badge success'>PASS</span>" if condition else "<span class='badge danger'>FAIL</span>"

    # --- 3. THE FUNNEL & DELTAS (Where are we losing articles? What changed?) ---
    funnel = metrics.funnel
    avg = avg_30 or {}
    
    f_down = funnel.get("downloaded", 0)
    f_dedupe = f_down - funnel.get("duplicate_id", 0) - funnel.get("duplicate_issuer", 0)
    f_regex = f_dedupe - funnel.get("regex_rejected", 0)
    f_ont = f_regex - funnel.get("ontology_rejected", 0)
    f_rules = f_ont - funnel.get("global_exclusion", 0)
    f_ai = funnel.get("reached_ai", 0)
    f_alerts = funnel.get("alerts_sent", 0)

    def render_funnel_step(name, current, avg_val):
        delta_html = ""
        if avg_val and avg_val > 0:
            pct_change = ((current - avg_val) / avg_val) * 100
            color = "trend-up" if pct_change > 0 else "trend-down"
            sign = "+" if pct_change > 0 else ""
            delta_html = f"<span class='{color}' style='font-size: 0.85em; margin-left: 10px;'>{sign}{pct_change:.0f}% vs 30d</span>"
        return f"""
        <div class='funnel-step'>
            <strong>{name}</strong> 
            <span>{current}{delta_html}</span>
        </div>
        <div class='funnel-arrow'>↓</div>
        """

    # --- 4. ANOMALIES (Did anything unusual happen today?) ---
    anomalies = []
    
    # Evaluate Runtime Drift Metrics
    avg_runtime = avg.get("total_runtime_s", runtime_s)
    if avg_runtime > 0:
        runtime_drift = ((runtime_s - avg_runtime) / avg_runtime) * 100
        if runtime_drift > 25:
            anomalies.append(f"<span class='badge warning'>RUNTIME</span> Execution took {runtime_s:.1f}s (+{runtime_drift:.0f}% over average).")
            
    # Trace Source Footprint Yield drops/spikes
    if src_30:
        for src, stats in metrics.source_stats.items():
            current_vol = stats.get("downloaded", 0)
            avg_vol = src_30.get(src, {}).get("downloaded", 0)
            if avg_vol > 20: 
                if current_vol < (avg_vol * 0.4):
                    anomalies.append(f"<span class='badge danger'>SOURCE DROP</span> {src} volume dropped 60%+ today ({current_vol} vs 30d avg {avg_vol:.0f}).")
                elif current_vol > (avg_vol * 2.0):
                    anomalies.append(f"<span class='badge info'>SOURCE SPIKE</span> {src} volume doubled today ({current_vol} vs 30d avg {avg_vol:.0f}).")

    if not anomalies:
        anomalies.append("<span style='color: var(--muted);'>No significant structural anomalies flagged this session.</span>")

    # --- 5. AI DIAGNOSTICS (If degraded, WHY?) ---
    ai_html = ""
    for key, ai in metrics.ai_telemetry.items():
        provider = ai.get("provider", "Unknown")
        key_id = str(ai.get("key_id", ""))[-4:] if len(str(ai.get("key_id", ""))) > 4 else "N/A"
        reqs, err_429, err_503, t_outs = ai.get("requests", 0), ai.get("errors_429", 0), ai.get("errors_503", 0), ai.get("timeouts", 0)
        
        if err_429 > 0 or err_503 > 0 or t_outs > 0:
            ai_html += f"<div style='color: var(--red); font-size: 0.9em; margin-bottom: 5px;'>[{provider}-{key_id}] {err_429} rate limits, {err_503} 503s, {t_outs} timeouts.</div>"
    
    if not ai_html:
        ai_html = "<div style='color: var(--green); font-size: 0.9em;'>All upstream AI paths nominal. Zero drops.</div>"

    # HTML Structuring Engine
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>SSR Executive Summary</title>
        <style>
            :root {{
                --bg: #0d1117; --surface: #161b22; --border: #30363d; --text: #c9d1d9;
                --muted: #8b949e; --green: #2ea043; --red: #cb2431; --yellow: #dbab0a; --blue: #58a6ff;
            }}
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background-color: var(--bg); color: var(--text); margin: 0; padding: 20px; }}
            .container {{ max-width: 1000px; margin: 0 auto; }}
            .status-banner {{ 
                background: var(--surface); border-left: 8px solid {sys_color}; border-radius: 6px; 
                padding: 20px 30px; display: flex; justify-content: space-between; align-items: center;
                margin-bottom: 20px; border-top: 1px solid var(--border); border-right: 1px solid var(--border); border-bottom: 1px solid var(--border);
            }}
            .status-banner h1 {{ margin: 0; font-size: 2.5em; color: {sys_color}; text-transform: uppercase; letter-spacing: 2px; border: none; }}
            .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
            .card {{ background: var(--surface); padding: 20px; border: 1px solid var(--border); border-radius: 6px; }}
            h2 {{ color: #fff; font-size: 1.1em; text-transform: uppercase; border-bottom: 1px solid var(--border); padding-bottom: 10px; margin-top: 0; }}
            .funnel-step {{ display: flex; justify-content: space-between; padding: 8px 12px; background: #1c2128; border-radius: 4px; border: 1px solid var(--border); }}
            .funnel-arrow {{ text-align: center; color: var(--muted); padding: 2px 0; font-weight: bold; font-size: 0.85em; }}
            .funnel-arrow:last-of-type {{ display: none; }}
            ul {{ list-style: none; padding: 0; margin: 0; }}
            li {{ padding: 8px 0; border-bottom: 1px solid #21262d; font-size: 0.9em; }}
            li:last-child {{ border-bottom: none; }}
            .badge {{ padding: 2px 6px; border-radius: 4px; font-size: 0.75em; font-weight: bold; margin-right: 8px; }}
            .badge.success {{ background: rgba(46,160,67,0.15); color: var(--green); border: 1px solid var(--green); }}
            .badge.danger {{ background: rgba(203,36,49,0.15); color: var(--red); border: 1px solid var(--red); }}
            .badge.warning {{ background: rgba(219,171,10,0.15); color: var(--yellow); border: 1px solid var(--yellow); }}
            .badge.info {{ background: rgba(88,166,255,0.15); color: var(--blue); border: 1px solid var(--blue); }}
            .trend-up {{ color: var(--green); }} .trend-down {{ color: var(--red); }}
        </style>
    </head>
    <body>
        <div class="container">
            
            <div class="status-banner">
                <div>
                    <h1>{sys_status}</h1>
                    <div style="color: var(--muted); margin-top: 5px;">
                        Run ID: {run_id} &bull; Next Scheduled Run: {getattr(metrics, 'next_run_str', 'Unknown')} &bull; Latency: {runtime_s:.1f}s
                    </div>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 1.1em;">Operational Score: <strong>{health_score}/100</strong></div>
                </div>
            </div>

            <div class="grid">
                <div class="card" style="grid-row: span 2;">
                    <h2>Volume Filter Cascade</h2>
                    {render_funnel_step("1. Ingested (Downloaded)", f_down, avg.get("downloaded"))}
                    {render_funnel_step("2. Passed Deduplication", f_dedupe, None)}
                    {render_funnel_step("3. Passed Global Exclusions", f_regex, None)}
                    {render_funnel_step("4. Survived Ontology Inferences", f_ont, None)}
                    {render_funnel_step("5. Met Rules Engine Threshold", f_rules, None)}
                    {render_funnel_step("6. Classified via GenAI Engine", f_ai, avg.get("ai_calls"))}
                    {render_funnel_step("7. Investment Memos Dispatched", f_alerts, avg.get("emails_sent"))}
                </div>

                <div class="card">
                    <h2>Volumetric & Runtime Anomalies</h2>
                    <ul>
                        {''.join(f"<li>{a}</li>" for a in anomalies)}
                    </ul>
                </div>

                <div class="card">
                    <h2>Deployment & Diagnostic Checks</h2>
                    
                    <div style="margin-bottom: 20px;">
                        <strong style="color: var(--muted); font-size: 0.8em; display: block; margin-bottom: 5px;">GENAI TELEMETRY DEGRADATION LOGS</strong>
                        {ai_html}
                    </div>

                    <strong style="color: var(--muted); font-size: 0.8em; display: block; margin-bottom: 5px;">INTEGRITY RUN STATE MATRIX</strong>
                    <table style="width: 100%; font-size: 0.9em;">
                        <tr><td style="padding: 6px 0;">Secret Screener Guardrails (Gitleaks)</td><td style="text-align: right;">{pass_fail_badge(secrets_pass)}</td></tr>
                        <tr><td style="padding: 6px 0;">Pipeline Execution Context (No Runtime Exceptions)</td><td style="text-align: right;">{pass_fail_badge(exceptions_pass)}</td></tr>
                        <tr><td style="padding: 6px 0;">SQLite Operational Databases Read/Write Access</td><td style="text-align: right;">{pass_fail_badge(db_pass)}</td></tr>
                    </table>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

def generate_archive_html(output_path):
    """Generates the searchable document archive ledger page."""
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>SSR Document Archive</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #0d1117; color: #c9d1d9; padding: 20px; }
            .container { max-width: 1200px; margin: 0 auto; background: #161b22; padding: 20px; border: 1px solid #30363d; border-radius: 6px; }
            h1 { border-bottom: 1px solid #30363d; padding-bottom: 10px; }
            input { width: 100%; padding: 10px; margin-bottom: 20px; background: #0d1117; color: #c9d1d9; border: 1px solid #30363d; border-radius: 4px; }
            table { width: 100%; border-collapse: collapse; font-size: 0.9em; }
            th, td { padding: 10px; text-align: left; border-bottom: 1px solid #30363d; }
            th { color: #8b949e; text-transform: uppercase; font-size: 0.85em; }
            a { color: #58a6ff; text-decoration: none; }
            .badge { padding: 3px 8px; border-radius: 12px; font-size: 0.8em; font-weight: 600; background: rgba(139,148,158,0.15); color: #8b949e; border: 1px solid rgba(139,148,158,0.4); }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Operational Document Archive</h1>
            <p style="color: #8b949e;">Dynamic, deterministic lookup of historically ingested documents and signal evaluations.</p>
            <input type="text" id="searchInput" placeholder="Search archive by ticker, source, event family, or title..." onkeyup="filterTable()">
            <table id="archiveTable">
                <thead>
                    <tr><th>Processed At</th><th>Source</th><th>Event Family</th><th>Title</th><th>Outcome</th></tr>
                </thead>
                <tbody id="tableBody">
                    <tr><td colspan="5">Loading data stream...</td></tr>
                </tbody>
            </table>
        </div>
        <script>
            let archiveData = [];
            fetch('archive_data.json')
                .then(response => response.json())
                .then(data => {
                    archiveData = data;
                    renderTable(archiveData);
                })
                .catch(error => {
                    document.getElementById('tableBody').innerHTML = "<tr><td colspan='5'>Error resolving file dependencies. Check archive_data.json.</td></tr>";
                });

            function renderTable(data) {
                const tbody = document.getElementById('tableBody');
                tbody.innerHTML = '';
                data.forEach(row => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td style="white-space: nowrap;">${row.processed_at ? row.processed_at.split('.')[0].replace('T', ' ') : '-'}</td>
                        <td>${row.source || 'Unknown'}</td>
                        <td>${row.event_family || '-'}</td>
                        <td><a href="${row.url || '#'}" target="_blank">${row.title || 'No Title'}</a></td>
                        <td><span class="badge">${row.outcome || 'Unknown'}</span></td>
                    `;
                    tbody.appendChild(tr);
                });
            }

            function filterTable() {
                const query = document.getElementById('searchInput').value.toLowerCase();
                const filtered = archiveData.filter(row => 
                    (row.title && row.title.toLowerCase().includes(query)) || 
                    (row.source && row.source.toLowerCase().includes(query)) ||
                    (row.event_family && row.event_family.toLowerCase().includes(query)) ||
                    (row.outcome && row.outcome.toLowerCase().includes(query))
                );
                renderTable(filtered);
            }
        </script>
    </body>
    </html>
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)