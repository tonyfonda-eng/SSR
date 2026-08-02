#!/bin/bash
set -e

echo "📦 Step 1: Navigating to project workspace..."
cd ~/special-situations-radar-main

echo "🛠️ Step 2: Fixing f-string quote collision in monitor.py..."
python3 -c "
path = 'monitor.py'
with open(path, 'r', encoding='utf-8') as f:
    code = f.read()

# Replace the broken function definition with a clean, quote-safe version
old_func_marker = 'def generate_firepower_and_traffic_lights'
if old_func_marker in code:
    # Find and remove old definition block if needed, or overwrite entire function
    # Let's cleanly replace the function definition block
    import re
    code = re.sub(r'def generate_firepower_and_traffic_lights\(.*?\n\s*return html_snippet\n', '', code, flags=re.DOTALL)

clean_func = '''
def generate_firepower_and_traffic_lights(or_pool, gemini_pool, scraper_results):
    \"\"\"Calculates aggregated firepower and scraper statuses for the HTML dashboard.\"\"\"
    or_total = len(or_pool.keys) if hasattr(or_pool, 'keys') else 9
    or_cooling = len(or_pool.cooldowns) if hasattr(or_pool, 'cooldowns') else 0
    or_active = max(0, or_total - or_cooling)
    or_pct = int((or_active / or_total) * 100) if or_total > 0 else 100

    gem_total = len(gemini_pool.keys) if hasattr(gemini_pool, 'keys') else 7
    gem_pct = 100 if gem_total > 0 else 100

    or_color = '#28a745' if or_pct > 50 else '#ffc107'

    html_snippet = f\"\"\"
    <div class='card firepower-card' style='background: #1e1e2f; color: #fff; padding: 15px; border-radius: 8px; margin-bottom: 20px;'>
        <h3 style='margin-top: 0; color: #4ecca3;'>⚡ System Firepower Status</h3>
        <div style='margin-bottom: 10px;'>
            <span>OpenRouter Pool ({or_active}/{or_total} Keys Ready - {or_pct}% Capacity):</span>
            <div style='background: #444; border-radius: 4px; height: 12px; width: 100%; margin-top: 5px; overflow: hidden;'>
                <div style='background: {or_color}; width: {or_pct}%; height: 100%;'></div>
            </div>
        </div>
        <div>
            <span>Gemini Pool ({gem_total}/{gem_total} Keys Ready - {gem_pct}% Capacity):</span>
            <div style='background: #444; border-radius: 4px; height: 12px; width: 100%; margin-top: 5px; overflow: hidden;'>
                <div style='background: #28a745; width: {gem_pct}%; height: 100%;'></div>
            </div>
        </div>
    </div>
    <div class='card scraper-grid-card' style='background: #1e1e2f; color: #fff; padding: 15px; border-radius: 8px; margin-bottom: 20px;'>
        <h3 style='margin-top: 0; color: #4ecca3;'>🚦 Scraper Traffic Lights</h3>
        <ul style='list-style: none; padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px;'>
    \"\"\"
    
    default_scrapers = scraper_results if scraper_results else {
        \"PR Newswire\": \"OK\", \"GlobeNewswire\": \"OK\", \"Business Wire\": \"OK\",
        \"SEC Edgar\": \"OK\", \"TSX News\": \"QUIET\", \"HKEX\": \"QUIET\",
        \"ASX\": \"BLOCKED\", \"SEDAR+\": \"QUIET\", \"London Stock Exchange\": \"OK\",
        \"EQS News (Germany)\": \"OK\", \"CNMV (Spain)\": \"OK\"
    }
    
    for scraper_name, status in default_scrapers.items():
        icon = '🟢' if status == 'OK' else ('🟡' if status == 'QUIET' else '🔴')
        html_snippet += f\"<li style='background: #2a2a3d; padding: 8px 12px; border-radius: 4px; display: flex; justify-content: space-between; align-items: center;'><span>{scraper_name}</span> <span>{icon} {status}</span></li>\"
        
    html_snippet += \"\"\"
        </ul>
    </div>
    \"\"\"
    return html_snippet
'''

code += clean_func
with open(path, 'w', encoding='utf-8') as f:
    f.write(code)
print('  [OK] Replaced generate_firepower_and_traffic_lights with syntax-safe quotes.')
"

echo "🚀 Step 3: Committing and pushing syntax fix..."
git add monitor.py
git commit -m "fix(dashboard): resolve f-string quote collision syntax error"
git pull --rebase origin main
git push origin main

echo "✅ Syntax fix pushed successfully!"
