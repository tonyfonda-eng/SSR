#!/bin/bash
set -e

echo "📦 Step 1: Navigating to project workspace..."
cd ~/special-situations-radar-main

echo "🛠️ Step 2: Adding initialise_database alias to src/database.py..."
python3 -c "
path = 'src/database.py'
with open(path, 'r', encoding='utf-8') as f:
    code = f.read()

if 'initialise_database =' not in code:
    code += '\n\n# Alias for compatibility with monitor.py imports\ninitialise_database = init_db\n'
    with open(path, 'w', encoding='utf-8') as f:
        f.write(code)
    print('  [OK] Added initialise_database alias.')
else:
    print('  [INFO] Alias already exists.')
"

echo "🚀 Step 3: Committing and pushing..."
git add src/database.py
git commit -m "fix(db): add initialise_database alias for import compatibility"
git pull --rebase origin main
git push origin main

echo "✅ Fix pushed successfully!"
