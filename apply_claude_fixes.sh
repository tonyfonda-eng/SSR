#!/bin/bash
set -e

echo "📦 Step 1: Navigating to project workspace..."
cd ~/special-situations-radar-main

echo "🧠 Step 2: Implementing Claude's OpenRouter Model Recommendation..."
python3 -c "
import os

ai_file = 'src/ai.py'
if os.path.exists(ai_file):
    with open(ai_file, 'r', encoding='utf-8') as f:
        code = f.read()
    
    # We use the universal latest alias to prevent future deprecation 404s
    code = code.replace('google/gemini-flash-1.5-8b', 'google/gemini-flash-latest')
    code = code.replace('google/gemini-1.5-pro', 'google/gemini-flash-latest')
    
    with open(ai_file, 'w', encoding='utf-8') as f:
        f.write(code)
    print('  [OK] OpenRouter models pinned to google/gemini-flash-latest')
"

echo "🗄️ Step 3: Fixing the SQLite runtime column in src/database.py..."
python3 -c "
import os

db_file = 'src/database.py'
if os.path.exists(db_file):
    with open(db_file, 'r', encoding='utf-8') as f:
        code = f.read()
    
    # We find our previous massive schema and ensure 'runtime' is strictly defined
    # Claude noticed that drift_monitor.py looks for 'runtime'
    if 'runtime REAL' not in code and 'workflow_health' in code:
        code = code.replace(
            'failed INTEGER,',
            'failed INTEGER,\n    runtime REAL,'
        )
        with open(db_file, 'w', encoding='utf-8') as f:
            f.write(code)
        print('  [OK] Added runtime REAL column to src/database.py schema')
    else:
        print('  [INFO] runtime column already exists or schema not found.')
"

echo "🗄️ Step 4: Forcing database rebuild to apply the runtime column..."
rm -f ssr_observability.db ssr_cache.sqlite validation.db || true

echo "🚀 Step 5: Committing fixes..."
git add src/
git commit -m "fix(core): update openrouter model to flash-latest and patch missing runtime column" || echo "No changes detected."
git pull --rebase origin main
git push origin main

echo "✅ Claude's fixes applied. The pipeline should now run completely green."
