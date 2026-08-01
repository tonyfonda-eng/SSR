import json
import datetime
import os

def generate_dashboard_html(log_records, output_path="docs/index.html", metrics=None):
    """
    Generates a static HTML dashboard from the lifecycle log records.
    log_records is a list of dicts from SQLite.
    """
    
    # Calculate System Score
    health_score = 100
    if metrics:
        total_runtime = metrics.daily.get("total_runtime_s", 0)
        health_score = metrics.calculate_health_score(total_runtime)
        
    score_color = "var(--success)"
    if health_score < 80: score_color = "var(--warning)"
    if health_score < 50: score_color = "var(--danger)"

    # Top 10 Slowest
    sorted_logs = sorted(log_records, key=lambda x: x.get("processing_time_ms", 0), reverse=True)
    top_10 = sorted_logs[:10]
    
    top_10_html = ""
    for r in top_10:
        top_10_html += f"<tr><td>{r.get('source','')}</td><td>{r.get('title','')[:60]}...</td><td style='color: var(--danger); font-weight: bold;'>{r.get('processing_time_ms',0)} ms</td></tr>"

    html_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SSR Operations Centre</title>
    <style>
        :root {
            --bg-color: #0f172a;
            --panel-bg: #1e293b;
            --text-color: #f1f5f9;
            --border-color: #334155;
            --accent: #3b82f6;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --gray: #64748b;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            margin: 0;
            padding: 20px;
        }
        .header-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        h1 {
            font-size: 1.8rem;
            margin: 0;
        }
        .subtitle {
            color: var(--gray);
            font-size: 0.9rem;
        }
        .score-card {
            background-color: var(--panel-bg);
            border: 1px solid var(--border-color);
            padding: 15px 25px;
            border-radius: 8px;
            text-align: center;
        }
        .score-value {
            font-size: 2.5rem;
            font-weight: bold;
            color: SCORE_COLOR;
        }
        .score-label {
            font-size: 0.8rem;
            color: var(--gray);
            text-transform: uppercase;
            letter-spacing: 0.1em;
        }
        .grid-2 {
            display: grid;
            grid-template-columns: 1fr;
            gap: 20px;
            margin-bottom: 20px;
        }
        .panel {
            background-color: var(--panel-bg);
            border-radius: 8px;
            border: 1px solid var(--border-color);
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
            padding: 15px;
        }
        .panel h2 {
            font-size: 1.1rem;
            margin-top: 0;
            margin-bottom: 10px;
            color: var(--gray);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        .table-container {
            overflow-x: auto;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.85rem;
            white-space: nowrap;
        }
        th, td {
            padding: 10px 12px;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
        }
        th {
            background-color: rgba(0,0,0,0.2);
            font-weight: 600;
            cursor: pointer;
            user-select: none;
            color: var(--gray);
            text-transform: uppercase;
            font-size: 0.75rem;
            letter-spacing: 0.05em;
        }
        th:hover {
            color: var(--text-color);
        }
        tr:hover td {
            background-color: rgba(255,255,255,0.02);
        }
        a {
            color: var(--accent);
            text-decoration: none;
        }
        a:hover {
            text-decoration: underline;
        }
        .badge {
            padding: 3px 6px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
        }
        .status-alert { background-color: rgba(16, 185, 129, 0.2); color: var(--success); }
        .status-drop { background-color: rgba(239, 68, 68, 0.2); color: var(--danger); }
        .status-archived { background-color: rgba(100, 116, 139, 0.2); color: var(--gray); }
        
        .stage-cell {
            font-family: monospace;
            color: var(--accent);
        }
        .search-bar {
            width: 100%;
            padding: 10px;
            margin-bottom: 15px;
            background-color: rgba(0,0,0,0.2);
            border: 1px solid var(--border-color);
            border-radius: 4px;
            color: var(--text-color);
            box-sizing: border-box;
        }
    </style>
</head>
<body>
    <div class="header-row">
        <div>
            <h1>SSR Operations Centre</h1>
            <div class="subtitle">Rolling 14-Day View | Generated: {GEN_TIME}</div>
        </div>
        <div class="score-card">
            <div class="score-value">{HEALTH_SCORE}</div>
            <div class="score-label">System Health</div>
        </div>
    </div>
    
    <div class="grid-2">
        <div class="panel">
            <h2>Pathological Cases (Top 10 Slowest Articles)</h2>
            <div class="table-container">
                <table>
                    <thead>
                        <tr><th>Source</th><th>Headline</th><th>Processing Time</th></tr>
                    </thead>
                    <tbody>
                        {TOP_10_ROWS}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    
    <div class="panel">
        <h2>Pipeline Execution Log</h2>
        <input type="text" id="searchInput" class="search-bar" placeholder="Search across all columns (e.g., AAPL, Rejected, regex)..." onkeyup="filterTable()">
        <div class="table-container">
            <table id="logTable">
                <thead>
                    <tr>
                        <th onclick="sortTable(0)">Timestamp ↕</th>
                        <th onclick="sortTable(1)">Source ↕</th>
                        <th onclick="sortTable(2)">Headline ↕</th>
                        <th onclick="sortTable(3)">Country ↕</th>
                        <th onclick="sortTable(4)">Lang ↕</th>
                        <th onclick="sortTable(5)">Doc Type ↕</th>
                        <th onclick="sortTable(6)">Issuer ↕</th>
                        <th onclick="sortTable(7)">Event ↕</th>
                        <th onclick="sortTable(8)">Pipeline Stage ↕</th>
                        <th onclick="sortTable(9)">Outcome ↕</th>
                        <th onclick="sortTable(10)">Reason ↕</th>
                        <th onclick="sortTable(11)">AI Invoked ↕</th>
                        <th onclick="sortTable(12)">Time (ms) ↕</th>
                    </tr>
                </thead>
                <tbody>
                    {TABLE_ROWS}
                </tbody>
            </table>
        </div>
    </div>

    <script>
        function filterTable() {
            var input, filter, table, tr, td, i, j, txtValue;
            input = document.getElementById("searchInput");
            filter = input.value.toUpperCase();
            table = document.getElementById("logTable");
            tr = table.getElementsByTagName("tr");
            
            for (i = 1; i < tr.length; i++) {
                tr[i].style.display = "none";
                td = tr[i].getElementsByTagName("td");
                for (j = 0; j < td.length; j++) {
                    if (td[j]) {
                        txtValue = td[j].textContent || td[j].innerText;
                        if (txtValue.toUpperCase().indexOf(filter) > -1) {
                            tr[i].style.display = "";
                            break;
                        }
                    }
                }
            }
        }
        
        function sortTable(n) {
            var table, rows, switching, i, x, y, shouldSwitch, dir, switchcount = 0;
            table = document.getElementById("logTable");
            switching = true;
            dir = "asc"; 
            while (switching) {
                switching = false;
                rows = table.rows;
                for (i = 1; i < (rows.length - 1); i++) {
                    shouldSwitch = false;
                    x = rows[i].getElementsByTagName("TD")[n];
                    y = rows[i + 1].getElementsByTagName("TD")[n];
                    
                    var xVal = x.innerHTML.toLowerCase();
                    var yVal = y.innerHTML.toLowerCase();
                    
                    if (n === 12) { // numeric column
                        xVal = parseFloat(xVal) || 0;
                        yVal = parseFloat(yVal) || 0;
                    }
                    
                    if (dir == "asc") {
                        if (xVal > yVal) { shouldSwitch = true; break; }
                    } else if (dir == "desc") {
                        if (xVal < yVal) { shouldSwitch = true; break; }
                    }
                }
                if (shouldSwitch) {
                    rows[i].parentNode.insertBefore(rows[i + 1], rows[i]);
                    switching = true;
                    switchcount ++; 
                } else {
                    if (switchcount == 0 && dir == "asc") {
                        dir = "desc";
                        switching = true;
                    }
                }
            }
        }
    </script>
</body>
</html>"""

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
        rows_html += f'<td>{r.get("country", "")}</td>'
        rows_html += f'<td>{r.get("language", "")}</td>'
        rows_html += f'<td>{r.get("document_type", "")}</td>'
        rows_html += f'<td>{r.get("issuer", "")}</td>'
        rows_html += f'<td>{r.get("event_family", "")}</td>'
        rows_html += f'<td class="stage-cell">{r.get("pipeline_stage", "")}</td>'
        rows_html += f'<td><span class="badge {outcome_class}">{outcome}</span></td>'
        rows_html += f'<td>{r.get("reason", "")}</td>'
        rows_html += f'<td>{ai_badge}</td>'
        rows_html += f'<td>{r.get("processing_time_ms", 0)}</td>'
        rows_html += "</tr>\n"

    final_html = html_template.replace("{TABLE_ROWS}", rows_html).replace("{GEN_TIME}", datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")).replace("SCORE_COLOR", score_color).replace("{HEALTH_SCORE}", str(health_score)).replace("{TOP_10_ROWS}", top_10_html)
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(final_html)
        
    print(f"[MONITORING] Dashboard generated at {output_path} with {len(log_records)} records.")
