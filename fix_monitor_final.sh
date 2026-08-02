#!/bin/bash
set -e

echo "📦 Step 1: Navigating to project workspace..."
cd ~/special-situations-radar-main

echo "🛠️ Step 2: Scrubbing nested print wrappers and resetting the monitor header..."
python3 -c "
import py_compile

with open('monitor.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

clean_lines = []
for line in lines:
    # Filter out any malformed lines containing nested prints or old init_db fragments
    if 'Special Situations Radar' in line or 'init_db' in line:
        continue
    clean_lines.append(line)

# Re-insert clean database initialization and banner at an appropriate top-level execution spot
final_lines = []
inserted = False
for line in clean_lines:
    if not inserted and ('if __name__' in line or 'def main' in line or 'parser = ' in line):
        final_lines.append('from src.database import init_db\n')
        final_lines.append('init_db()\n\n')
        final_lines.append('print(\"=== Special Situations Radar v1.0.0 ===\")\n')
        inserted = True
    final_lines.append(line)

if not inserted:
    final_lines.insert(0, 'from src.database import init_db\ninit_db()\nprint(\"=== Special Situations Radar v1.0.0 ===\")\n')

with open('monitor.py', 'w', encoding='utf-8') as f:
    f.writelines(final_lines)

print('🔍 Step 3: Validating syntax compilation...')
py_compile.compile('monitor.py', doraise=True)
print('  [SUCCESS] monitor.py compiled successfully!')
"

echo "🚀 Step 4: Committing and pushing the final fix..."
git add monitor.py
git commit -m "fix(syntax): remove nested print wrappers and establish clean monitor startup"
git pull --rebase origin main
git push origin main

echo "✅ Clean version deployed successfully!"
