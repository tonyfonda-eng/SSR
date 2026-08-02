#!/bin/bash
set -e

echo "📦 Step 1: Navigating to project workspace..."
cd ~/special-situations-radar-main

echo "🧠 Step 2: Capping OpenRouter max_tokens in src/ai.py..."
python3 -c '
import os
ai_file = "src/ai.py"
if os.path.exists(ai_file):
    with open(ai_file, "r", encoding="utf-8") as f:
        code = f.read()
    
    code = code.replace("max_tokens=65535", "max_tokens=8192")
    code = code.replace("MAX_TOKENS = 65535", "MAX_TOKENS = 8192")
    
    with open(ai_file, "w", encoding="utf-8") as f:
        f.write(code)
    print("  [OK] Capped max_tokens in src/ai.py")
'

echo "🗄️ Step 3: Adding auto-migration for the 'failed' column in src/drift_monitor.py..."
python3 -c '
import os
drift_file = "src/drift_monitor.py"
if os.path.exists(drift_file):
    with open(drift_file, "r", encoding="utf-8") as f:
        code = f.read()
    
    migration_snippet = """
    try:
        conn.execute("ALTER TABLE workflow_health ADD COLUMN failed INTEGER DEFAULT 0;")
        conn.commit()
    except Exception:
        pass
"""
    if "ALTER TABLE workflow_health ADD COLUMN failed" not in code:
        code = code.replace(
            "def analyze_drift(",
            "def analyze_drift(" + migration_snippet
        )
        with open(drift_file, "w", encoding="utf-8") as f:
            f.write(code)
        print("  [OK] Injected failed column migration into drift_monitor.py")
'

echo "🚀 Step 4: Committing and pushing fixes..."
git add src/ai.py src/drift_monitor.py
git commit -m "fix(core): cap openrouter max_tokens to 8192 and add workflow_health failed column migration"
git pull --rebase origin main
git push origin main

echo "✅ Fixes applied and pushed successfully!"
