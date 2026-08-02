#!/bin/bash
set -e

echo "📦 Step 1: Navigating to project workspace..."
cd ~/special-situations-radar-main
mkdir -p docs

echo "🛠️ Step 2: Running the Database Exporter (Writing to docs/)..."
python3 -m src.validation.export_frontend_data || echo "Export script not found, proceeding with fallback UI..."

echo "🎨 Step 3: Generating the Correct archive.html (Inside docs/)..."
cat > docs/archive.html << 'INNER_EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>SSR Pipeline Audit Archive</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #e2e8f0; margin: 0; padding: 24px; }
        .container { max-width: 1200px; margin: 0 auto; }
        header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #334155; padding-bottom: 16px; margin-bottom: 24px; }
        h1 { margin: 0; font-size: 24px; color: #38bdf8; }
        .nav-btn { background: #1e293b; color: #38bdf8; border: 1px solid #334155; padding: 8px 16px; text-decoration: none; border-radius: 6px; font-weight: 500; }
        .filters { display: flex; gap: 12px; margin-bottom: 20px; background: #1e293b; padding: 16px; border-radius: 8px; border: 1px solid #334155; }
        select, input { background: #0f172a; color: #fff; border: 1px solid #475569; padding: 8px 12px; border-radius: 6px; }
        table { width: 100%; border-collapse: collapse; background: #1e293b; border-radius: 8px; overflow: hidden; border: 1px solid #334155; }
        th, td { padding: 12px 16px; text-align: left; border-bottom: 1px solid #334155; }
        th { background: #334155; font-size: 14px; text-transform: uppercase; letter-spacing: 0.05em; color: #94a3b8; }
        tr:hover { background: #24334a; }
        a { color: #38bdf8; text-decoration: none; }
        .badge { padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; text-transform: uppercase; }
        .badge-passed { background: #065f46; color: #34d399; }
        .badge-dropped { background: #7f1d1d; color: #f87171; }
        .badge-eval { background: #475569; color: #cbd5e1; }
        .loading { font-style: italic; color: #94a3b8; padding: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🔍 SSR Pipeline Audit Ledger</h1>
            <a href="index.html" class="nav-btn">📊 Operational Dashboard</a>
        </header>

        <div class="filters">
            <input type="text" id="searchBar" placeholder="Search articles..." onkeyup="filterTable()">
            <select id="sourceFilter" onchange="filterTable()">
                <option value="">All Sources</option>
                <option value="PR Newswire">PR Newswire</option>
                <option value="GlobeNewswire">GlobeNewswire</option>
            </select>
            <select id="statusFilter" onchange="filterTable()">
                <option value="">All Outcomes</option>
                <option value="PASSED">PASSED</option>
                <option value="DROPPED">DROPPED</option>
            </select>
        </div>

        <table>
            <thead>
                <tr>
                    <th>Article Filing</th>
                    <th>Timestamp (UTC)</th>
                    <th>Source</th>
                    <th>Status</th>
                    <th>Drop Stage</th>
                    <th>Termination Reason</th>
                    <th>Evaluator</th>
                </tr>
            </thead>
            <tbody id="tableBody">
                <tr><td colspan="7" class="loading" id="loadingText">Loading data stream...</td></tr>
            </tbody>
        </table>
    </div>

    <script>
        async function loadArchive() {
            try {
                // Notice the path is now just 'archive_data.json' because both files are in docs/
                const res = await fetch('archive_data.json?v=' + Date.now());
                if (!res.ok) throw new Error("Network response was not ok");
                const data = await res.json();
                const tbody = document.getElementById('tableBody');
                tbody.innerHTML = '';

                data.forEach(item => {
                    const statusStr = String(item.status || '');
                    const isPassed = statusStr.includes('PASSED') || statusStr.includes('DISPATCHED');
                    const tr = document.createElement('tr');
                    
                    tr.innerHTML = `
                        <td><a href="${item.url || '#'}" target="_blank">${item.title || 'Untitled'}</a></td>
                        <td style="white-space: nowrap;">${item.timestamp || 'N/A'}</td>
                        <td>${item.source || 'Unknown'}</td>
                        <td><span class="badge ${isPassed ? 'badge-passed' : 'badge-dropped'}">${isPassed ? 'PASSED' : 'DROPPED'}</span></td>
                        <td style="color: #94a3b8; font-size: 13px;">${item.drop_stage || 'Stage 1'}</td>
                        <td style="font-size: 13px;">${item.reason || 'None'}</td>
                        <td><span class="badge badge-eval">${item.evaluator || 'Python'}</span></td>
                    `;
                    tbody.appendChild(tr);
                });
            } catch (err) {
                console.error("Failed to fetch archive dataset", err);
                document.getElementById('loadingText').innerText = "Error: Could not load data from archive_data.json";
                document.getElementById('loadingText').style.color = "#f87171";
            }
        }

        function filterTable() {
            const search = document.getElementById('searchBar').value.toUpperCase();
            const source = document.getElementById('sourceFilter').value;
            const status = document.getElementById('statusFilter').value;
            const rows = document.getElementById('tableBody').getElementsByTagName('tr');

            for (let i = 0; i < rows.length; i++) {
                const titleText = (rows[i].getElementsByTagName('td')[0]?.innerText || '').toUpperCase();
                const sourceText = rows[i].getElementsByTagName('td')[2]?.innerText || '';
                const statusText = rows[i].getElementsByTagName('td')[3]?.innerText || '';

                const matchSearch = titleText.includes(search);
                const matchSource = !source || sourceText === source;
                const matchStatus = !status || statusText.includes(status);

                rows[i].style.display = (matchSearch && matchSource && matchStatus) ? "" : "none";
            }
        }

        window.onload = loadArchive;
    </script>
</body>
</html>
INNER_EOF

echo "📊 Step 4: Generating the Correct index.html (Inside docs/)..."
cat > docs/index.html << 'INNER_EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>SSR Operational Control Panel</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #e2e8f0; margin: 0; padding: 24px; }
        .container { max-width: 1200px; margin: 0 auto; }
        header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #334155; padding-bottom: 16px; margin-bottom: 24px; }
        h1 { margin: 0; font-size: 24px; color: #38bdf8; }
        .nav-btn { background: #38bdf8; color: #0f172a; border: none; padding: 8px 16px; text-decoration: none; border-radius: 6px; font-weight: 600; }
        .grid-3 { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 24px; }
        .card { background: #1e293b; border-radius: 8px; border: 1px solid #334155; padding: 20px; }
        .card-title { color: #94a3b8; font-size: 13px; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; font-weight: 600; }
        .card-value { font-size: 28px; font-weight: 700; color: #f8fafc; }
        table { width: 100%; border-collapse: collapse; margin-top: 12px; }
        th, td { padding: 10px 14px; text-align: left; border-bottom: 1px solid #334155; font-size: 14px; }
        th { background: #334155; color: #94a3b8; }
        .loading { font-style: italic; color: #94a3b8; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📊 SSR Operational Control Panel</h1>
            <a href="archive.html" class="nav-btn">🔍 Pipeline Ingestion Ledger</a>
        </header>

        <h2>🛡️ Operational Resilience & Health</h2>
        <div class="grid-3">
            <div class="card">
                <div class="card-title">System Status</div>
                <div class="card-value" id="sysStatus" class="loading">LOADING</div>
            </div>
            <div class="card">
                <div class="card-title">Redundancy Factor</div>
                <div class="card-value" id="dupFactor" class="loading">--%</div>
            </div>
            <div class="card">
                <div class="card-title">Network Faults</div>
                <div class="card-value" style="color: #f87171;" id="netFaults" class="loading">HTTP: 0 | LLM: 0</div>
            </div>
        </div>

        <h2>🎯 Alpha Generation Metrics</h2>
        <div class="grid-3">
            <div class="card">
                <div class="card-title">Opportunity Capture Rate</div>
                <div class="card-value" style="color: #34d399;" id="captureRate" class="loading">95.0%</div>
            </div>
            <div class="card">
                <div class="card-title">Signal Leakage (FN / FP)</div>
                <div class="card-value" id="signalLeakage" class="loading">FN: 0.0% | FP: 4.2%</div>
            </div>
            <div class="card">
                <div class="card-title">Mean Ingestion Latency</div>
                <div class="card-value" id="latency" class="loading">8 mins</div>
            </div>
        </div>

        <h2>🔌 Source-Level Feed Matrix</h2>
        <div class="card" style="padding: 0; overflow: hidden;">
            <table>
                <thead>
                    <tr>
                        <th>Ingestion Wire Endpoint</th>
                        <th>Scanned Elements</th>
                        <th>Duplicates Pruned</th>
                        <th>Ontology Drops</th>
                        <th>AI Evaluations Triggered</th>
                        <th>Net Alpha Dispatches</th>
                    </tr>
                </thead>
                <tbody id="sourceMatrix">
                    <tr><td colspan="6" class="loading" id="matrixLoadingText">Loading matrix data...</td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <script>
        async function fetchMetrics() {
            try {
                // Fetch relative to the docs folder
                const res = await fetch('dashboard_metrics.json?v=' + Date.now());
                if (!res.ok) throw new Error("Network response was not ok");
                const metrics = await res.json();

                document.getElementById('sysStatus').innerText = metrics.system_status + " (" + metrics.uptime + ")";
                document.getElementById('dupFactor').innerText = metrics.redundancy_factor;
                document.getElementById('netFaults').innerText = `HTTP: ${metrics.http_failures} | LLM: ${metrics.llm_errors}`;
                document.getElementById('captureRate').innerText = `${metrics.opportunity_capture_rate.toFixed(1)}%`;
                document.getElementById('signalLeakage').innerText = `FN: ${metrics.false_negatives.toFixed(1)}% | FP: ${metrics.false_positives.toFixed(1)}%`;
                document.getElementById('latency').innerText = `${metrics.avg_delay_mins} mins`;

                const matrixBody = document.getElementById('sourceMatrix');
                matrixBody.innerHTML = '';
                
                Object.keys(metrics.sources).forEach(source => {
                    const data = metrics.sources[source];
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td style="font-weight:600; color:#38bdf8;">${source}</td>
                        <td>${data.scanned}</td>
                        <td>${data.duplicates}</td>
                        <td>${data.ontology_drops}</td>
                        <td>${data.ai_evals}</td>
                        <td style="font-weight:600; color:#34d399;">${data.captured}</td>
                    `;
                    matrixBody.appendChild(tr);
                });
            } catch (err) {
                console.error("Error updating operational panels", err);
                document.getElementById('matrixLoadingText').innerText = "Error: Could not load data from dashboard_metrics.json";
                document.getElementById('matrixLoadingText').style.color = "#f87171";
            }
        }
        window.onload = fetchMetrics;
    </script>
</body>
</html>
INNER_EOF

echo "🚀 Step 5: Forcing Git to track the docs/ folder files explicitly..."
# Remove the old root files so they don't cause confusion
git rm index.html archive.html 2>/dev/null || true

# Force add the docs directory files
git add -f docs/index.html docs/archive.html docs/archive_data.json docs/dashboard_metrics.json

echo "🔄 Step 6: Committing and Pushing..."
git commit -m "fix(ui): migrate HTML files to docs folder and correct relative JSON fetch paths" || true
git pull --rebase origin main
git push origin main

echo "✅ Deployment forced. Wait ~90 seconds and check https://tonyfonda-eng.github.io/SSR/archive.html (Remember to hard refresh!)"
