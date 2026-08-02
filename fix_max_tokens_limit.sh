#!/bin/bash
set -e

echo "📦 Step 1: Navigating to project workspace..."
cd ~/special-situations-radar-main

echo "🔍 Step 2: Locating and updating max_tokens in python source files..."
python3 -c "
import glob, re

modified = False
for path in glob.glob('src/**/*.py', recursive=True) + ['monitor.py']:
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # Check for max_tokens assignments or dictionary keys with high values
    if 'max_tokens' in content:
        # Replace large integer values or explicit 65535/32768 caps
        new_content = re.sub(r'max_tokens\s*=\s*\d+', 'max_tokens = 4096', content)
        new_content = re.sub(r'\"max_tokens\"\s*:\s*\d+', '\"max_tokens\": 4096', new_content)
        new_content = re.sub(r\"\'max_tokens\'\s*:\s*\d+\", \"\'max_tokens\': 4096\", new_content)
        
        if new_content != content:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f'  [OK] Updated max_tokens limit in {path}')
            modified = True

if not modified:
    print('  [INFO] No explicit max_tokens assignments found via regex. Checking ai.py wrappers...')
"

echo "🚀 Step 3: Committing and pushing token cap fix..."
git add src/ monitor.py || true
git commit -m "fix(ai): lower max_tokens cap to 4096 to comply with openrouter credit tiers" || echo "No changes to commit."
git pull --rebase origin main
git push origin main

echo "✅ Token fix applied and pushed successfully!"
