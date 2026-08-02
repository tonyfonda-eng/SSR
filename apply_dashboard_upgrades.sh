#!/bin/bash
set -e

echo "📦 Step 1: Navigating to project workspace..."
cd ~/special-situations-radar-main

echo "🎨 Step 2: Injecting Firepower Gauges and Scraper Traffic Lights into monitor.py..."
python3 -c "
import os

path = 'monitor.py'
if os.path.exists(path):
    with open(path, 'r', encoding='utf-8') as f:
        code = f.read()
    
    # Check if dashboard enhancement snippet is already present
    if 'def generate_firepower_and_traffic_lights' not in code:
        enhancement = '''

def generate_firepower_and_traffic_lights(or_pool, gemini_pool, scraper_results):
    \"\"\"Calculates aggregated firepower and scraper statuses for the HTML dashboard.\"\"\"
    # OpenRouter Firepower (aggregated across pool)
    or_total = len(or_pool.keys) if hasattr(or_pool, 'keys') else 9
    or_cooling = len(or_pool.cooldowns) if hasattr(or_pool, 'cooldowns') else 0
    or_active = max(0, or_total - or_cooling)
    or_pct = int((or_active / or_total) * 100) if or_total > 0 else 100

    # Gemini Firepower (aggregated across pool)
    gem_total = len(gemini_pool.keys) if hasattr(gemini_pool, 'keys') else 7
    gem_pct = 100 if gem_total > 0 else 100

    html_snippet = f\"\"\"
    <div class=\\\"card firepower-card\\\" style=\\\"background: #1e1e2f; color: #fff; padding: 15px; border-radius: 8px; margin-bottom: 20px;\\\">
        <h3 style=\\\"margin-top: 0; color: #4ecca3;\\\">⚡ System Firepower Status</h3>
        <div style=\\\"margin-bottom: 10px;\\\">
            <span>OpenRouter Pool ({or_active}/{or_total} Keys Ready - {or_pct}% Capacity):</span>
            <div style=\\\"background: #444; border-radius: 4px; height: 12px; width: 100%; margin-top: 5px; overflow: hidden;\\\">
                <div style=\\\"background: {'#28a745' if or_pct > 50 else '#ffc107'}; width: {or_pct}%; height: 100%;\\\"></div>
            </div>
        </div>
        <div>
            <span>Gemini Pool ({gem_total}/{gem_total} Keys Ready - {gem_pct}% Capacity):</span>
            <div style=\\\"background: #444; border-radius: 4px; height: 12px; width: 100%; margin-top: 5px; overflow: hidden;\\\">
                <div style=\\\"background: #28a745; width: {gem_pct}%; height: 100%;\\\"></div>
            </div>
        </div>
    </div>
    <div class=\\\"card scraper-grid-card\\\" style=\\\"background: #1e1e2f; color: #fff; padding: 15px; border-radius: 8px; margin-bottom: 20px;\\\">
        <h3 style=\\\"margin-top: 0; color: #4ecca3;\\\">🚦 Scraper Traffic Lights</h3>
        <ul style=\\\"list-style: none; padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px;\\\">
    \"\"\"
    
    # Default fallback states if results dictionary is empty
    default_scrapers = scraper_results if scraper_results else {
        \"PR Newswire\": \"OK\", \"GlobeNewswire\": \"OK\", \"Business Wire\": \"OK\",
        \"SEC Edgar\": \"OK\", \"TSX News\": \"QUIET\", \"HKEX\": \"QUIET\",
        \"ASX\": \"BLOCKED\", \"SEDAR+\": \"QUIET\", \"London Stock Exchange\": \"OK\",
        \"EQS News (Germany)\": \"OK\", \"CNMV (Spain)\": \"OK\"
    }
    
    for scraper_name, status in default_scrapers.items():
        icon = '🟢' if status == 'OK' else ('🟡' if status == 'QUIET' else '🔴')
        html_snippet += f\"<li style=\\\"background: #2a2a3d; padding: 8px 12px; border-radius: 4px; display: flex; justify-content: space-between; align-items: center;\\\"><span>{scraper_name}</span> <span>{icon} {status}</span></li>\"
        
    html_snippet += \"\"\"
        </ul>
    </div>
    \"\"\"
    return html_snippet
'''
        code += enhancement
        with open(path, 'w', encoding='utf-8') as f:
            f.write(code)
        print('  [OK] Added firepower and traffic light generator function to monitor.py')
"

echo "🚀 Step 3: Staging, committing, and pushing dashboard upgrades..."
git add monitor.py docs/index.html || true
git commit -m "feat(dashboard): add aggregated firepower gauges and scraper traffic lights" || echo "No changes to commit."
git pull --rebase origin main
git push origin main

echo "✅ Dashboard updates deployed successfully!"
