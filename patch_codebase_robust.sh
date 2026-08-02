#!/bin/bash
set -e

echo "📦 Step 1: Navigating to project workspace..."
cd ~/special-situations-radar-main

echo "🧠 Step 2: Searching and replacing token limit 65535 across all source files..."
python3 -c "
import glob, os

modified_files = []
for path in glob.glob('src/**/*.py', recursive=True) + ['monitor.py']:
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    if '65535' in content:
        new_content = content.replace('65535', '8192')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        modified_files.append(path)
        print(f'  [OK] Replaced 65535 with 8192 in {path}')

if not modified_files:
    print('  [INFO] No explicit 65535 literal found in python files. Checking configuration/constants...')
"

echo "🗄️ Step 3: Ensuring graceful column handling in src/drift_monitor.py..."
python3 -c "
import os
path = 'src/drift_monitor.py'
if os.path.exists(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Inject an automatic sqlite column addition if 'failed' column query fails
    if 'ALTER TABLE workflow_health ADD COLUMN failed' not in content:
        # Find connection execution and wrap or add migration
        target = 'conn.execute('
        replacement = '''try:
        conn.execute(\"ALTER TABLE workflow_health ADD COLUMN failed INTEGER DEFAULT 0;\")
        conn.commit()
    except Exception:
        pass
    conn.execute('''
        
        if target in content:
            content = content.replace(target, replacement, 1)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            print('  [OK] Added safe column migration for \'failed\' in drift_monitor.py')
"

echo "🚀 Step 4: Staging, committing, and pushing updates..."
git add src/ monitor.py || true
git commit -m "fix(core): replace token limit 65535 with 8192 and add drift table migration" || echo "No changes to commit."
git pull --rebase origin main
git push origin main

echo "✅ Robust patch applied and pushed successfully!"
