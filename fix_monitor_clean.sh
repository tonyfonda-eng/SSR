#!/bin/bash
set -e

echo "📦 Step 1: Navigating to project workspace..."
cd ~/special-situations-radar-main

echo "🛠️ Step 2: Cleaning up the dangling quote in monitor.py..."
python3 -c "
import py_compile

with open('monitor.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix any malformed banner print statement or dangling quote
content = content.replace('=== Special Situations Radar v1.0.0 ===\"', 'print(\"=== Special Situations Radar v1.0.0 ===\")')
content = content.replace('=== Special Situations Radar v1.0.0 ===', 'print(\"=== Special Situations Radar v1.0.0 ===\")')

# Ensure we don't have double prints if it was partially fixed
while 'print(print(\"===' in content:
    content = content.replace('print(print(\"===', 'print(\"===')

with open('monitor.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('🔍 Step 3: Validating syntax compilation...')
py_compile.compile('monitor.py', doraise=True)
print('  [SUCCESS] monitor.py compiled successfully!')
"

echo "🚀 Step 4: Committing and pushing..."
git add monitor.py
git commit -m "fix(syntax): resolve dangling quote around banner print in monitor.py"
git pull --rebase origin main
git push origin main

echo "✅ Syntax cleaned and successfully deployed!"
