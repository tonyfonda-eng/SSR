import os
import json
import datetime

def generate_dashboard_html(logs, output_path="docs/index.html", metrics=None, avg_30=None, src_30=None):
    """Generates the comprehensive Operations Centre dashboard combining Vitals, Funnels, and Surprises."""
    
    # Extract operational metrics
    total_runtime = metrics.daily.get("total_runtime_s", 0) if metrics else 0
    articles_downloaded = metrics.daily.get("downloaded", 0) if metrics else 0
    emails_sent = metrics.daily.get("emails_sent", 0) if metrics else 0
    ai_calls = metrics.daily.get("ai_calls", 0) if metrics else 0
    ai_successes = metrics.daily.get("ai_successes", 0) if metrics else 0
    exceptions = metrics.exceptions if metrics else []
    
    # Calculate Health Score (0-100)
    health_score = 100
    if exceptions:
        health_score -= (len(exceptions) * 15)
    if ai_calls > 0 and (ai_successes / ai_calls) < 0.8:
        health_score -= 20
    health_score = max(0, health_score)

    # Funnel metrics extraction
    funnel = metrics.daily.get("funnel", {}) if metrics else {}
    
    # Deterministic "Surprises" Engine
    surprises = []
    if articles_downloaded > 500 and emails_sent == 0:
        surprises.append("⚠️ High ingestion volume today, but zero email alerts generated (High noise or strict filtering).")
    if exceptions:
        surprises.append(f"⚠️ System encountered {len(exceptions)} runtime exception(s) during execution.")
    if total_runtime > 600:
        surprises.append("⚠️ Pipeline runtime exceeded 10 minutes, indicating potential network throttling.")
    if not surprises:
        surprises.append("✅ All deterministic checks nominal. No unusual anomalies detected today.")

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SSR Operations Centre Cockpit</title>
    <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
</head>
<body class="bg-gray-900 text-gray-100 font-sans leading-normal tracking-normal">

    <nav class="bg-gray-800 border-b border-gray-700 px-6 py-4 flex justify-between items-center">
        <div class="flex items-center space-x-3">
            <i class="fa-solid fa-radar text-blue-500 text-2xl"></i>
            <span class="text-xl font-bold tracking-wider">SSR OPERATIONS CENTRE</span>
        </div>
        <div class="flex space-x-4">
            <a href="index.html" class="bg-blue-600 px-4 py-2 rounded text-sm font-semibold hover:bg-blue-500 transition">Cockpit</a>
            <a href="archive.html" class="bg-gray-700 px-4 py-2 rounded text-sm font-semibold hover:bg-gray-600 transition">Data Archive</a>
        </div>
    </nav>

    <div class="container mx-auto px-6 py-8">

        <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
            <div class="bg-gray-800 border border-gray-700 rounded-lg p-5 shadow">
                <div class="text-gray-400 text-xs font-bold uppercase tracking-wider">Overall Health Score</div>
                <div class="text-4xl font-extrabold mt-2 {'text-green-400' if health_score > 80 else 'text-yellow-400' if health_score > 50 else 'text-red-500'}">
                    {health_score}/100
                </div>
                <div class="text-xs text-gray-400 mt-2">Based on exceptions & API success rates</div>
            </div>

            <div class="bg-gray-800 border border-gray-700 rounded-lg p-5 shadow">
                <div class="text-gray-400 text-xs font-bold uppercase tracking-wider">Pipeline Runtime</div>
                <div class="text-3xl font-bold mt-2 text-blue-400">{total_runtime:.1f}s</div>
                <div class="text-xs text-gray-400 mt-2">Execution timestamp: {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</div>
            </div>

            <div class="bg-gray-800 border border-gray-700 rounded-lg p-5 shadow">
                <div class="text-gray-400 text-xs font-bold uppercase tracking-wider">Articles Downloaded</div>
                <div class="text-3xl font-bold mt-2 text-purple-400">{articles_downloaded:,}</div>
                <div class="text-xs text-gray-400 mt-2">Filtered through global rules</div>
            </div>

            <div class="bg-gray-800 border border-gray-700 rounded-lg p-5 shadow">
                <div class="text-gray-400 text-xs font-bold uppercase tracking-wider">Alerts Dispatched</div>
                <div class="text-3xl font-bold mt-2 text-green-400">{emails_sent}</div>
                <div class="text-xs text-gray-400 mt-2">Actionable special situations</div>
            </div>
        </div>

        <div class="bg-gray-800 border-l-4 border-blue-500 p-5 rounded-r-lg mb-8 shadow">
            <h2 class="text-lg font-bold text-blue-400 mb-2"><i class="fa-solid fa-bolt mr-2"></i>What surprises me today? (Daily Briefing)</h2>
            <ul class="list-disc list-inside space-y-1 text-gray-300 text-sm">
                {"".join([f"<li>{s}</li>" for s in surprises])}
            </ul>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
            <div class="bg-gray-800 border border-gray-700 rounded-lg p-6 shadow">
                <h2 class="text-xl font-bold mb-4 text-gray-200"><i class="fa-solid fa-filter mr-2 text-blue-400"></i>Pipeline Conversion Funnel</h2>
                <div class="space-y-4">
                    <div>
                        <div class="flex justify-between text-sm mb-1">
                            <span>Raw Articles Downloaded</span>
                            <span class="font-bold">{articles_downloaded}</span>
                        </div>
                        <div class="w-full bg-gray-700 rounded-full h-2.5">
                            <div class="bg-blue-600 h-2.5 rounded-full" style="width: 100%"></div>
                        </div>
                    </div>
                    <div>
                        <div class="flex justify-between text-sm mb-1">
                            <span>Reached AI Verification</span>
                            <span class="font-bold">{ai_calls}</span>
                        </div>
                        <div class="w-full bg-gray-700 rounded-full h-2.5">
                            <div class="bg-purple-600 h-2.5 rounded-full" style="width: {min(100, (ai_calls / max(1, articles_downloaded)) * 100):.1f}%"></div>
                        </div>
                    </div>
                    <div>
                        <div class="flex justify-between text-sm mb-1">
                            <span>Actionable Alerts Generated</span>
                            <span class="font-bold">{emails_sent}</span>
                        </div>
                        <div class="w-full bg-gray-700 rounded-full h-2.5">
                            <div class="bg-green-600 h-2.5 rounded-full" style="width: {min(100, (emails_sent / max(1, articles_downloaded)) * 100 * 10):.1f}%"></div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="bg-gray-800 border border-gray-700 rounded-lg p-6 shadow">
                <h2 class="text-xl font-bold mb-4 text-gray-200"><i class="fa-solid fa-triangle-exclamation mr-2 text-yellow-400"></i>Recent Exceptions & Errors</h2>
                <div class="overflow-y-auto max-h-48 space-y-2 text-sm">
                    {"".join([f"<div class='bg-gray-700 p-2 rounded text-red-300'><strong>{exc.get('exc_type')}</strong>: {exc.get('module')}</div>" for exc in exceptions]) if exceptions else "<div class='text-gray-400 italic'>No exceptions recorded in this session. System running cleanly.</div>"}
                </div>
            </div>
        </div>

        <div class="bg-gray-800 border border-gray-700 rounded-lg p-6 shadow mb-8">
            <h2 class="text-xl font-bold mb-4 text-gray-200"><i class="fa-solid fa-list mr-2 text-blue-400"></i>Recent Ingested Activity</h2>
            <div class="overflow-x-auto">
                <table class="min-w-full text-left text-sm text-gray-300">
                    <thead class="bg-gray-700 text-gray-200 uppercase text-xs">
                        <tr>
                            <th class="py-2 px-3">Timestamp</th>
                            <th class="py-2 px-3">Source</th>
                            <th class="py-2 px-3">Issuer</th>
                            <th class="py-2 px-3">Title</th>
                            <th class="py-2 px-3">Event Family</th>
                            <th class="py-2 px-3">Outcome</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join([f"<tr class='border-b border-gray-700'><td class='py-2 px-3'>{log.get('timestamp')}</td><td class='py-2 px-3'>{log.get('source')}</td><td class='py-2 px-3 font-semibold text-blue-300'>{log.get('issuer')}</td><td class='py-2 px-3'><a href='{log.get('url', '#')}' class='text-blue-400 hover:underline' target='_blank'>{log.get('title')}</a></td><td class='py-2 px-3'>{log.get('event_family')}</td><td class='py-2 px-3'>{log.get('outcome')}</td></tr>" for log in logs]) if logs else "<tr><td colspan='6' class='text-center py-4 text-gray-400 italic'>No recent activity logged.</td></tr>"}
                    </tbody>
                </table>
            </div>
        </div>

    </div>
</body>
</html>
"""
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"[MONITORING] Operations Centre cockpit successfully generated at {output_path}")

def generate_archive_html(output_path="docs/archive.html"):
    """Generates the DataTables archive front-end page."""
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SSR Data Archive</title>
    <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.datatables.net/1.11.5/css/jquery.dataTables.min.css">
</head>
<body class="bg-gray-900 text-gray-100 p-6">
    <nav class="flex justify-between items-center mb-6">
        <h1 class="text-2xl font-bold">SSR Historical Archive</h1>
        <a href="index.html" class="bg-blue-600 px-4 py-2 rounded text-sm font-semibold hover:bg-blue-500">Back to Cockpit</a>
    </nav>
    <div class="bg-gray-800 p-6 rounded-lg shadow">
        <p class="text-gray-400">Loading ingested data records from archive_data.json...</p>
    </div>
</body>
</html>
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)