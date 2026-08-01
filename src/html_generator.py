import datetime

def generate_dashboard_html(logs, output_path, metrics, avg_30=None, src_30=None):
    """Generates the institutional-grade Operations Centre dashboard."""
    
    now_str = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    health_score = metrics.calculate_health_score(metrics.daily.get("total_runtime_s", 0))
    
    # Determine Health Color
    if health_score >= 90:
        health_color = "#2ea043" # Green
        health_status = "HEALTHY"
    elif health_score >= 75:
        health_color = "#dbab0a" # Yellow
        health_status = "DEGRADED"
    else:
        health_color = "#cb2431" # Red
        health_status = "CRITICAL"

    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>SSR Operations Centre</title>
        <style>
            :root {{
                --bg: #0d1117;
                --surface: #161b22;
                --border: #30363d;
                --text: #c9d1d9;
                --muted: #8b949e;
                --green: #2ea043;
                --red: #cb2431;
                --yellow: #dbab0a;
                --blue: #58a6ff;
            }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
                background-color: var(--bg);
                color: var(--text);
                margin: 0;
                padding: 20px;
                line-height: 1.5;
            }}
            .container {{ max-width: 1400px; margin: 0 auto; }}
            h1, h2, h3 {{ color: #ffffff; border-bottom: 1px solid var(--border); padding-bottom: 8px; }}
            .header-panel {{
                display: flex; justify-content: space-between; align-items: center;
                background: var(--surface); padding: 20px; border: 1px solid var(--border); border-radius: 6px;
                margin-bottom: 20px;
            }}
            .health-score {{ font-size: 2.5em; font-weight: bold; color: {health_color}; }}
            .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; margin-bottom: 20px; }}
            .card {{ background: var(--surface); padding: 20px; border: 1px solid var(--border); border-radius: 6px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 0.9em; }}
            th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid var(--border); }}
            th {{ color: var(--muted); font-weight: 600; text-transform: uppercase; font-size: 0.8em; }}
            tr:hover {{ background-color: #1c2128; }}
            .badge {{ padding: 3px 8px; border-radius: 12px; font-size: 0.8em; font-weight: 600; }}
            .badge.success {{ background: rgba(46,160,67,0.15); color: var(--green); border: 1px solid rgba(46,160,67,0.4); }}
            .badge.danger {{ background: rgba(203,36,49,0.15); color: var(--red); border: 1px solid rgba(203,36,49,0.4); }}
            .badge.warning {{ background: rgba(219,171,10,0.15); color: var(--yellow); border: 1px solid rgba(219,171,10,0.4); }}
            .badge.info {{ background: rgba(88,166,255,0.15); color: var(--blue); border: 1px solid rgba(88,166,255,0.4); }}
            .trend-up {{ color: var(--green); }}
            .trend-down {{ color: var(--red); }}
            .drift-warning {{ color: var(--yellow); font-weight: bold; }}
            a {{ color: var(--blue); text-decoration: none; }}
            a:hover {{ text-decoration: underline; }}
            .footer {{ text-align: center; margin-top: 40px; color: var(--muted); font-size: 0.8em; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header-panel">
                <div>
                    <h1 style="border: none; padding: 0; margin: 0;">Special Situations Radar</h1>
                    <div style="color: var(--muted); margin-top: 5px;">Operations Centre | Phase 3 Architecture</div>
                </div>
                <div style="text-align: right;">
                    <div class="health-score">{health_score}/100</div>
                    <div>System Status: <strong>{health_status}</strong></div>
                    <div style="color: var(--muted); font-size: 0.8em; margin-top: 5px;">Last Updated: {now_str}</div>
                </div>
            </div>

            <div class="grid">
                <div class="card">
                    <h2>Pipeline Funnel</h2>
                    <table>
                        <tr><th>Stage</th><th>Volume</th><th>30d Avg</th><th>Drift</th></tr>
    """
    
    # Render Funnel Data
    funnel = metrics.funnel
    
    def render_funnel_row(stage_name, current_val, avg_val=None):
        drift_html = "-"
        avg_str = "-"
        if avg_val and avg_val > 0:
            avg_str = f"{avg_val:.1f}"
            drift_pct = ((current_val - avg_val) / avg_val) * 100
            drift_class = "trend-up" if drift_pct > 0 else "trend-down"
            # Warn if drift is massive
            if abs(drift_pct) > 50 and current_val > 10:
                drift_html = f"<span class='drift-warning'>{drift_pct:+.1f}% ⚠</span>"
            else:
                drift_html = f"<span class='{drift_class}'>{drift_pct:+.1f}%</span>"
                
        return f"<tr><td>{stage_name}</td><td>{current_val}</td><td>{avg_str}</td><td>{drift_html}</td></tr>"

    # Map the exact funnel sequence
    html += render_funnel_row("1. Downloaded", funnel.get("downloaded", 0), avg_30.get("downloaded", 0) if avg_30 else None)
    html += render_funnel_row("2. Survived Deduplication", funnel.get("downloaded", 0) - funnel.get("duplicate_id", 0) - funnel.get("duplicate_issuer", 0))
    html += render_funnel_row("3. Passed Global Exclusions", funnel.get("downloaded", 0) - funnel.get("global_exclusion", 0))
    html += render_funnel_row("4. Reached Rules Engine", funnel.get("downloaded", 0) - funnel.get("regex_rejected", 0) - funnel.get("ontology_rejected", 0))
    html += render_funnel_row("5. Reached AI", funnel.get("reached_ai", 0), avg_30.get("ai_calls", 0) if avg_30 else None)
    html += render_funnel_row("6. Playbook Validated", funnel.get("reached_ai", 0) - funnel.get("ai_rejected_private", 0) - funnel.get("ai_rejected_false_positive", 0) - funnel.get("playbook_rejected", 0))
    html += render_funnel_row("7. Alerts Sent", funnel.get("alerts_sent", 0), avg_30.get("emails_sent", 0) if avg_30 else None)

    html += """
                    </table>
                </div>

                <div class="card">
                    <h2>AI Telemetry</h2>
                    <table>
                        <tr><th>Provider</th><th>Reqs</th><th>Success</th><th>Max Latency</th><th>429s</th></tr>
    """
    
    for key, ai in metrics.ai_telemetry.items():
        provider = ai.get("provider", "Unknown")
        reqs = ai.get("requests", 0)
        success = ai.get("success", 0)
        latency = ai.get("max_latency", 0.0)
        rate_limits = ai.get("errors_429", 0)
        
        success_rate = (success / reqs * 100) if reqs > 0 else 0
        rate_class = "danger" if success_rate < 90 else "success"
        
        html += f"""
            <tr>
                <td>{provider}</td>
                <td>{reqs}</td>
                <td><span class='badge {rate_class}'>{success_rate:.1f}%</span></td>
                <td>{latency:.2f}s</td>
                <td>{rate_limits}</td>
            </tr>
        """
        
    if not metrics.ai_telemetry:
        html += "<tr><td colspan='5' style='text-align:center;'>No AI calls this run</td></tr>"

    html += """
                    </table>
                    
                    <h3 style="margin-top: 20px;">System Exceptions</h3>
    """
    
    if metrics.exceptions:
        for exc in metrics.exceptions:
            html += f"<div style='color: var(--red); font-family: monospace; font-size: 0.8em; margin-bottom: 5px;'>[{exc['severity']}] {exc['exc_type']} in {exc['module']}</div>"
    else:
        html += "<div style='color: var(--green); font-family: monospace; font-size: 0.8em;'>Zero runtime exceptions detected.</div>"

    html += """
                </div>
            </div>

            <div class="card" style="margin-bottom: 20px;">
                <h2>Source Quality Matrix</h2>
                <table>
                    <tr><th>Source</th><th>Volume</th><th>To AI</th><th>Alerts</th><th>Signal Rate</th><th>Processing (ms)</th></tr>
    """
    
    # Sort sources by Signal Rate descending
    sorted_sources = sorted(
        metrics.source_stats.items(), 
        key=lambda item: (item[1]["alerts"] / item[1]["downloaded"]) if item[1]["downloaded"] > 0 else 0, 
        reverse=True
    )
    
    for src, st in sorted_sources:
        vol = st.get("downloaded", 0)
        to_ai = st.get("reached_ai", 0)
        alerts = st.get("alerts", 0)
        proc_time = st.get("processing_time_sum", 0) / max(1, st.get("processed_count", 1))
        
        signal_rate = (alerts / vol * 100) if vol > 0 else 0.0
        
        if signal_rate > 5.0: sig_class = "success"
        elif signal_rate > 0.0: sig_class = "info"
        else: sig_class = "muted"
        
        html += f"""
            <tr>
                <td>{src}</td>
                <td>{vol}</td>
                <td>{to_ai}</td>
                <td>{alerts}</td>
                <td><span class='badge {sig_class}'>{signal_rate:.2f}%</span></td>
                <td>{proc_time:.0f}ms</td>
            </tr>
        """
        
    if not sorted_sources:
        html += "<tr><td colspan='6' style='text-align:center;'>No sources processed this run</td></tr>"
        
    html += """
                </table>
            </div>

            <div class="card">
                <h2>Lifecycle Telemetry (Last 100)</h2>
                <table>
                    <tr><th>Time (UTC)</th><th>Source</th><th>Event Family</th><th>Issuer</th><th>Outcome</th><th>Slowest Stage</th></tr>
    """
    
    for log in logs[:100]:
        outcome = log.get("outcome", "Unknown")
        if "Alert Sent" in outcome: badge = "success"
        elif "Archived" in outcome: badge = "warning"
        elif "Dropped" in outcome: badge = "danger"
        else: badge = "info"
        
        title_truncated = log.get("title", "")[:40] + "..." if len(log.get("title", "")) > 40 else log.get("title", "")
        
        html += f"""
            <tr>
                <td>{log.get('timestamp', '').split()[-2]}</td>
                <td>{log.get('source', 'Unknown')}</td>
                <td>{log.get('event_family', '-')}</td>
                <td title="{log.get('title', '')}"><a href="{log.get('url', '#')}" target="_blank">{log.get('issuer', 'Unknown')}</a></td>
                <td><span class='badge {badge}'>{outcome}</span></td>
                <td>{log.get('slowest_stage', '-')}</td>
            </tr>
        """

    html += """
                </table>
            </div>
            
            <div class="footer">
                SSR Operations Centre &bull; Institutional Monitoring &bull; Deterministic Execution
            </div>
        </div>
    </body>
    </html>
    """

    import os
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
        

def generate_archive_html(output_path):
    """Generates the static lightweight archive index for searching past events."""
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
            table { width: 100%; border-collapse: collapse; }
            th, td { padding: 10px; text-align: left; border-bottom: 1px solid #30363d; }
            th { color: #8b949e; }
            a { color: #58a6ff; text-decoration: none; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Document Archive</h1>
            <p style="color: #8b949e;">A complete ledger of ingested articles. Data is loaded dynamically.</p>
            <input type="text" id="searchInput" placeholder="Search archive by title, source, or date..." onkeyup="filterTable()">
            
            <table id="archiveTable">
                <thead>
                    <tr><th>Processed At</th><th>Source</th><th>Title</th><th>Published</th></tr>
                </thead>
                <tbody id="tableBody">
                    <tr><td colspan="4">Loading data...</td></tr>
                </tbody>
            </table>
        </div>

        <script>
            // Extremely lightweight deterministic script purely for rendering the local JSON payload. No frameworks.
            let archiveData = [];
            
            fetch('archive_data.json')
                .then(response => response.json())
                .then(data => {
                    archiveData = data;
                    renderTable(archiveData);
                })
                .catch(error => {
                    document.getElementById('tableBody').innerHTML = "<tr><td colspan='4'>Error loading data.</td></tr>";
                });

            function renderTable(data) {
                const tbody = document.getElementById('tableBody');
                tbody.innerHTML = '';
                data.forEach(row => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td>${row.processed_at.split('.')[0].replace('T', ' ')}</td>
                        <td>${row.source}</td>
                        <td><a href="${row.url}" target="_blank">${row.title}</a></td>
                        <td>${row.published}</td>
                    `;
                    tbody.appendChild(tr);
                });
            }

            function filterTable() {
                const query = document.getElementById('searchInput').value.toLowerCase();
                const filtered = archiveData.filter(row => 
                    row.title.toLowerCase().includes(query) || 
                    row.source.toLowerCase().includes(query) ||
                    row.processed_at.includes(query)
                );
                renderTable(filtered);
            }
        </script>
    </body>
    </html>
    """
    
    import os
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)