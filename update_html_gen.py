import re

with open("src/html_generator.py", "r") as f:
    content = f.read()

# Define the replacement string
replacement = '''def generate_screening_log_html(output_path):
    screening_css = """
        .table-wrapper { background: var(--surface); border: 1px solid var(--border); overflow-x: auto; }
        th { background: var(--surface-subtle); position: sticky; top: 0; z-index: 10; }
        .filter-bar { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 12px; align-items: center; }
        .filter-bar select, .filter-bar input { background: var(--surface); border: 1px solid var(--border); color: var(--text); padding: 6px 10px; font-size: 0.85em; font-family: inherit; }
        .filter-bar input { flex: 1; min-width: 200px; }
        .filter-bar label { font-size: 0.7em; text-transform: uppercase; color: var(--muted); letter-spacing: 0.4px; }
        .outcome-passed { color: var(--green); font-weight: 700; }
        .outcome-dropped { color: var(--red); font-weight: 700; }
        .reason-tag { font-family: var(--mono); color: var(--yellow); font-size: 0.85em; background: rgba(219,171,10,0.1); padding: 2px 6px; border-radius: 3px; }
        .headline-cell { max-width: 420px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .headline-cell a { color: var(--text); text-decoration: none; }
        .headline-cell a:hover { color: var(--blue); text-decoration: underline; }
        .result-count { color: var(--muted); font-size: 0.8em; margin-bottom: 8px; }
        .badge { display: inline-block; padding: 3px 6px; border-radius: 4px; font-size: 0.7em; font-weight: 600; text-transform: uppercase; background: var(--surface-subtle); border: 1px solid var(--border); margin-right: 4px; }
        .success { color: var(--green); border-color: rgba(66,211,146,0.3); }
        .warn { color: var(--yellow); border-color: rgba(219,171,10,0.3); }
        .mode-fallback { color: var(--yellow); font-weight: 700; font-size: 0.8em; }
        .mode-rss { color: var(--muted); font-size: 0.8em; }
    """

    html = """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>Daily Master Log</title><style>__BASE_CSS__ __SCREENING_CSS__</style>__SORT_JS__</head>
    <body><div class="container">__NAV__<header><h1>Daily Master Log</h1></header>

    <div class="filter-bar">
        <div><label>News Source</label><br><select id="sourceFilter"><option value="">All Sources</option></select></div>
        <div><label>Drop Reason</label><br><select id="reasonFilter"><option value="">All Reasons</option></select></div>
        <div><label>Outcome</label><br><select id="outcomeFilter"><option value="">All</option><option value="PASSED">Passed</option><option value="DROPPED">Dropped</option></select></div>
        <div style="flex:1;"><label>Search (headline, source)</label><br><input type="text" id="searchBox" placeholder="Type to filter..."></div>
    </div>
    <div class="result-count" id="resultCount"></div>

    <div class="table-wrapper"><table id="screeningTable">
    <thead><tr><th>Timestamp (GMT)</th><th>Status</th><th>Source</th><th>Headline</th><th>Mode</th><th>Outcome</th><th>Final Stage</th><th>Drop Reason</th></tr></thead>
    <tbody id="tableBody"><tr><td colspan="8" style="text-align: center; color: var(--muted); padding: 30px;">Loading Master Log...</td></tr></tbody>
    </table></div></div>

    <script>
        let screeningData = [];
        const todayGMT = new Date().toISOString().split('T')[0];

        fetch('screening_log.json')
            .then(res => res.json())
            .then(data => {
                const allData = Array.isArray(data) ? data : (data.screening_log || []);
                // Filter to only show today's news
                screeningData = allData.filter(r => r.timestamp && r.timestamp.startsWith(todayGMT));
                populateFilters();
                renderTable();
            })
            .catch(err => {
                screeningData = [];
                renderTable();
            });

        function populateFilters() {
            const sources = [...new Set(screeningData.map(r => r.source).filter(Boolean))].sort();
            const sourceSel = document.getElementById('sourceFilter');
            sources.forEach(s => {
                const opt = document.createElement('option');
                opt.value = s; opt.textContent = s;
                sourceSel.appendChild(opt);
            });
            
            const reasons = [...new Set(screeningData.map(r => r.drop_reason).filter(Boolean))].sort();
            const reasonSel = document.getElementById('reasonFilter');
            reasons.forEach(r => {
                const opt = document.createElement('option');
                opt.value = r; opt.textContent = r;
                reasonSel.appendChild(opt);
            });
        }

        document.getElementById('sourceFilter').addEventListener('change', renderTable);
        document.getElementById('reasonFilter').addEventListener('change', renderTable);
        document.getElementById('outcomeFilter').addEventListener('change', renderTable);
        document.getElementById('searchBox').addEventListener('input', renderTable);

        function renderTable() {
            const tbody = document.getElementById('tableBody');
            const sourceVal = document.getElementById('sourceFilter').value;
            const reasonVal = document.getElementById('reasonFilter').value;
            const outcomeVal = document.getElementById('outcomeFilter').value;
            const searchVal = document.getElementById('searchBox').value.toLowerCase();

            let filtered = screeningData.filter(r => {
                if (sourceVal && r.source !== sourceVal) return false;
                if (reasonVal && r.drop_reason !== reasonVal) return false;
                if (outcomeVal && r.outcome !== outcomeVal) return false;
                if (searchVal) {
                    const hay = `${r.headline||''} ${r.source||''}`.toLowerCase();
                    if (!hay.includes(searchVal)) return false;
                }
                return true;
            });

            document.getElementById('resultCount').textContent = `Showing ${filtered.length} of ${screeningData.length} articles for today (${todayGMT})`;

            tbody.innerHTML = '';
            if (filtered.length === 0) {
                tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; padding:20px;">No articles match the current filters.</td></tr>';
                return;
            }

            filtered.forEach(r => {
                const tr = document.createElement('tr');
                const outcomeCls = r.outcome === 'PASSED' ? 'outcome-passed' : 'outcome-dropped';
                const reasonHtml = r.drop_reason ? `<span class="reason-tag">${r.drop_reason}</span>` : '';
                const modeCls = r.ingestion_mode === 'HTML_FALLBACK' ? 'mode-fallback' : 'mode-rss';
                const modeLabel = r.ingestion_mode === 'HTML_FALLBACK' ? 'FALLBACK' : (r.ingestion_mode || 'RSS');
                
                const statusHtml = r.drop_reason === 'dropped_hash_duplicate' 
                    ? '<span class="badge warn">DUPLICATE</span>' 
                    : '<span class="badge success">BRAND NEW</span>';
                
                tr.innerHTML = `<td>${r.timestamp || ''}</td>
                                <td>${statusHtml}</td>
                                <td>${r.source || 'Unknown'}</td>
                                <td class="headline-cell"><a href="${r.url || '#'}" target="_blank" title="${(r.headline||'').replace(/"/g,'&quot;')}">${r.headline || 'Untitled'}</a></td>
                                <td class="${modeCls}">${modeLabel}</td>
                                <td class="${outcomeCls}">${r.outcome || ''}</td>
                                <td>${r.final_stage || ''}</td>
                                <td>${reasonHtml}</td>`;
                tbody.appendChild(tr);
            });
        }
    </script></body></html>"""

    html = html.replace("__BASE_CSS__", BASE_CSS).replace("__SORT_JS__", SORT_JS).replace("__SCREENING_CSS__", screening_css).replace("__NAV__", render_nav("archive"))
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f: f.write(html)

# Alias for backward compatibility with monitor.py callers
generate_screening_html = generate_screening_log_html'''

content = re.sub(r'def generate_screening_log_html\(output_path\):.*generate_screening_html = generate_screening_log_html', replacement, content, flags=re.DOTALL)

with open("src/html_generator.py", "w") as f:
    f.write(content)
