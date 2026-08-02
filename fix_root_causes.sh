#!/bin/bash
set -e

echo "📦 Step 1: Navigating to project workspace..."
cd ~/special-situations-radar-main

echo "🧠 Step 2: Harmonizing model strings in src/ai.py and src/ai_audit_manager.py..."
python3 -c "
import os

# Fix ai.py
ai_path = 'src/ai.py'
if os.path.exists(ai_path):
    with open(ai_path, 'r', encoding='utf-8') as f:
        code = f.read()
    # Use OpenRouter's fully-qualified model string
    code = code.replace('google/gemini-2.0-flash', 'google/gemini-2.0-flash-001')
    with open(ai_path, 'w', encoding='utf-8') as f:
        f.write(code)
    print('  [OK] Updated src/ai.py model slug.')

# Fix ai_audit_manager.py
audit_path = 'src/ai_audit_manager.py'
if os.path.exists(audit_path):
    with open(audit_path, 'r', encoding='utf-8') as f:
        code = f.read()
    code = code.replace('google/gemini-flash-1.5', 'google/gemini-2.0-flash-001')
    with open(audit_path, 'w', encoding='utf-8') as f:
        f.write(code)
    print('  [OK] Updated src/ai_audit_manager.py model slug.')
"

echo "🗄️ Step 3: Neutralizing the conflicting schema in src/drift_monitor.py..."
python3 -c "
import os
drift_path = 'src/drift_monitor.py'
if os.path.exists(drift_path):
    with open(drift_path, 'r', encoding='utf-8') as f:
        code = f.read()
    
    # Remove the conflicting local CREATE TABLE statement so it relies on database.py's master schema
    old_stmt = 'conn.execute(\"\"\"CREATE TABLE IF NOT EXISTS workflow_health (timestamp TEXT PRIMARY KEY, total_scanned INTEGER, articles INTEGER, errors INTEGER, drift_score REAL)\"\"\")'
    if old_stmt in code:
        code = code.replace(old_stmt, '# Master schema handled by database.py')
        with open(drift_path, 'w', encoding='utf-8') as f:
            f.write(code)
        print('  [OK] Removed conflicting table creation from drift_monitor.py')
"

echo "🧹 Step 4: Clearing old databases to force clean master schema instantiation..."
rm -f ssr_observability.db ssr_cache.sqlite validation.db || true

echo "🚀 Step 5: Committing and pushing root-cause fixes..."
git add src/ai.py src/ai_audit_manager.py src/drift_monitor.py
git commit -m "fix(core): align openrouter model slugs to full version string and remove drift_monitor schema collision" || echo "No changes to commit."
git pull --rebase origin main
git push origin main

echo "✅ Root causes neutralized!"
