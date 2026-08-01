import json
import datetime

def generate_dashboard_html(log_records, output_path="docs/index.html"):
    """
    Generates a static HTML dashboard from the lifecycle log records.
    log_records is a list of tuples/dicts from SQLite.
    """
    
    html_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SSR Operational Dashboard</title>
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
        h1 {
            color: var(--text-color);
            font-size: 1.5rem;
            margin-bottom: 5px;
        }
        .subtitle {
            color: var(--gray);
            font-size: 0.9rem;
            margin-bottom: 20px;
        }
        .table-container {
            overflow-x: auto;
            background-color: var(--panel-bg);
            border-radius: 8px;
            border: 1px solid var(--border-color);
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
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
            background-color: var(--panel-bg);
            border: 1px solid var(--border-color);
            border-radius: 4px;
            color: var(--text-color);
            box-sizing: border-box;
        }
    </style>
</head>
<body>
    <h1>SSR Operational Monitoring</h1>
    <div class="subtitle">Rolling 14-Day View | Generated: {GEN_TIME}</div>
    
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
                    <th onclick="sortTable(8)">Stage Reached ↕</th>
                    <th onclick="sortTable(9)">Final Status ↕</th>
                    <th onclick="sortTable(10)">Drop Reason ↕</th>
                    <th onclick="sortTable(11)">Time (ms) ↕</th>
                </tr>
            </thead>
            <tbody>
                {TABLE_ROWS}
            </tbody>
        </table>
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
                    
                    if (n === 11) { // numeric column
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
        
        status = r.get("final_status", "")
        status_class = "status-archived"
        if "Alert" in status: status_class = "status-alert"
        elif "Drop" in status or "Reject" in status: status_class = "status-drop"
        
        rows_html += "<tr>"
        rows_html += f'<td>{r.get("timestamp", "")}</td>'
        rows_html += f'<td>{r.get("source", "")}</td>'
        rows_html += f'<td>{title_html}</td>'
        rows_html += f'<td>{r.get("country", "")}</td>'
        rows_html += f'<td>{r.get("language", "")}</td>'
        rows_html += f'<td>{r.get("document_type", "")}</td>'
        rows_html += f'<td>{r.get("issuer", "")}</td>'
        rows_html += f'<td>{r.get("event_family", "")}</td>'
        rows_html += f'<td class="stage-cell">{r.get("stage", "")}</td>'
        rows_html += f'<td><span class="badge {status_class}">{status}</span></td>'
        rows_html += f'<td>{r.get("drop_reason", "")}</td>'
        rows_html += f'<td>{r.get("processing_time_ms", 0)}</td>'
        rows_html += "</tr>\n"

    final_html = html_template.replace("{TABLE_ROWS}", rows_html).replace("{GEN_TIME}", datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"))
    
    import os
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(final_html)
        
    print(f"[MONITORING] Dashboard generated at {output_path} with {len(log_records)} records.")
