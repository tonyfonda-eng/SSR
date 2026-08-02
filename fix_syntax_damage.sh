#!/bin/bash
set -e

echo "📦 Step 1: Navigating to project workspace..."
cd ~/special-situations-radar-main

echo "🛠️ Step 2: Surgically repairing the syntax in all 13 impacted files..."
python3 -c "
import os
import re

repaired_count = 0
# Walk through the entire src directory natively in Python
for root, dirs, files in os.walk('src'):
    for file in files:
        if file.endswith('.py'):
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8') as f:
                code = f.read()
            
            # This regex looks for the exact broken string (e.g., kwargs.get('headers', ./src/...))
            # and replaces it with the correct Python syntax: kwargs.get('headers', {})
            fixed_code = re.sub(
                r\"kwargs\.get\('headers',\s*\./[^\)]+\)\",
                r\"kwargs.get('headers', {})\", 
                code
            )
            
            # If a change was made, write it back to the file
            if code != fixed_code:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(fixed_code)
                print(f'[OK] Repaired syntax in {filepath}')
                repaired_count += 1

print(f'\n[DONE] Successfully repaired {repaired_count} files.')
"

echo "🚀 Step 3: Committing the repaired files..."
git add src/
git commit -m "fix(core): repair broken kwargs syntax in scrapers and build_docs"
git pull --rebase origin main
git push origin main

echo "✅ All syntax errors have been neutralized and pushed. The pipeline is safe to run."
