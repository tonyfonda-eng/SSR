#!/bin/bash
set -e

echo "📦 Step 1: Navigating to repository..."
cd ~/special-situations-radar-main

echo "🛠️ Step 2: Surgically deleting the malformed line 519..."
# Delete line 519 exactly
sed -i '519d' monitor.py

echo "🔍 Step 3: Validating syntax..."
python3 -m py_compile monitor.py
echo "  [SUCCESS] Syntax compilation passed!"

echo "🚀 Step 4: Committing and pushing the final fix..."
git add monitor.py
git commit -m "fix(syntax): delete improperly indented duplicate print statement" || echo "No changes to commit."
git pull --rebase origin main
git push origin main

echo "✅ The rogue line is gone and the pipeline should run flawlessly."
