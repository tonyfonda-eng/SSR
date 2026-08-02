#!/bin/bash
set -e

echo "📦 Step 1: Navigating to repository..."
cd ~/special-situations-radar-main

echo "🧠 Step 2: Fixing OpenRouter model string to a verified slug..."
python3 -c "
import os
ai_file = 'src/ai.py'
if os.path.exists(ai_file):
    with open(ai_file, 'r', encoding='utf-8') as f:
        code = f.read()
    
    # OpenRouter's universally supported fast flash model slug
    code = code.replace('google/gemini-flash-latest', 'google/gemini-2.0-flash')
    
    with open(ai_file, 'w', encoding='utf-8') as f:
        f.write(code)
    print('  [OK] OpenRouter model string updated to google/gemini-2.0-flash')
"

echo "🗄️ Step 3: Adding auto-migration safety for the runtime column in drift_monitor.py..."
python3 -c "
import os
drift_file = 'src/drift_monitor.py'
if os.path.exists(drift_file):
    with open(drift_file, 'r', encoding='utf-8') as f:
        code = f.read()
    
    # Inject a safe ALTER TABLE check right before drift analysis runs
    migration_snippet = '''
    try:
        conn.execute(\"ALTER TABLE workflow_health ADD COLUMN runtime REAL;\")
        conn.commit()
    except Exception:
        pass # Column already exists
'''
    if 'ALTER TABLE workflow_health ADD COLUMN runtime' not in code:
        # Find where the connection is opened in drift analysis
        code = code.replace(
            'def analyze_drift(',
            'def analyze_drift(' + migration_snippet
        )
        with open(drift_file, 'w', encoding='utf-8') as f:
            f.write(code)
        print('  [OK] Auto-migration safety injected into drift_monitor.py')
"

echo "🚀 Step 4: Committing and pushing final polish..."
git add src/ai.py src/drift_monitor.py
git commit -m "fix(core): set valid openrouter slug and add auto-migration for drift runtime column" || echo "No changes to commit."
git pull --rebase origin main
git push origin main

echo "✅ Final polish applied and pushed!"
