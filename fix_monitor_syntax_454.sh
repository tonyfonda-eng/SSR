#!/bin/bash
set -e

echo "📦 Step 1: Navigating to project workspace..."
cd ~/special-situations-radar-main

echo "🛠️ Step 2: Fixing monitor.py line 454..."
python3 -c "
import py_compile

with open('monitor.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip_next = False
for i, line in enumerate(lines):
    # Target and remove the malformed injection around line 454
    if 'print(\"from src.database import init_db' in line:
        print(f'  [CLEANED] Removed malformed line {i+1}: {line.strip()}')
        continue
    
    # Ensure proper clean import if it was broken
    if '=== Special Situations Radar' in line and not any('init_db' in l for l in new_lines[-5:]):
        new_lines.append('from src.database import init_db\n')
        new_lines.append('init_db()\n\n')
        
    new_lines.append(line)

with open('monitor.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('🔍 Step 3: Validating syntax compilation...')
py_compile.compile('monitor.py', doraise=True)
print('  [SUCCESS] monitor.py compiled successfully!')
"

echo "🚀 Step 4: Committing and pushing the fix..."
git add monitor.py
git commit -m "fix(syntax): repair malformed init_db injection on line 454"
git pull --rebase origin main
git push origin main

echo "✅ Syntax repaired and pushed successfully!"
