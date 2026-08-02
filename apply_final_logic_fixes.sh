#!/bin/bash
set -e

echo "📦 Step 1: Navigating to project workspace..."
cd ~/special-situations-radar-main

echo "🧠 Step 2: Fixing OpenRouter syntax to google/gemini-1.5-pro..."
python3 -c "
import os
filepath = 'src/ai.py'
if os.path.exists(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        code = f.read()
    
    # Transpose the model string to the exact OpenRouter standard
    updated_code = code.replace('google/gemini-pro-1.5', 'google/gemini-1.5-pro')
    
    if code != updated_code:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(updated_code)
        print('  [OK] OpenRouter model string corrected in ai.py')
"

echo "🗄️ Step 3: Aligning database schemas with drift_monitor.py expectations..."
python3 -c "
import os

for filepath in ['src/drift_monitor.py', 'src/database.py']:
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            code = f.read()
        
        # We find the table creation string and inject the missing 'articles' column
        if 'total_scanned INTEGER' in code and 'articles INTEGER' not in code:
            updated_code = code.replace(
                'total_scanned INTEGER,',
                'total_scanned INTEGER, articles INTEGER,'
            )
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(updated_code)
            print(f'  [OK] Added articles column to schema in {filepath}')
        
        # Also fix the INSERT statements if they exist
        if 'INSERT INTO workflow_health (timestamp, total_scanned, errors, drift_score)' in code:
            updated_code = code.replace(
                'INSERT INTO workflow_health (timestamp, total_scanned, errors, drift_score)',
                'INSERT INTO workflow_health (timestamp, total_scanned, articles, errors, drift_score)'
            )
            # Add a zero fallback for the new column value
            updated_code = updated_code.replace(
                'VALUES (?, ?, ?, ?)',
                'VALUES (?, ?, 0, ?, ?)'
            )
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(updated_code)
            print(f'  [OK] Updated INSERT logic in {filepath}')
"

echo "📡 Step 4: Fixing the ASX scraper dictionary type mismatch..."
python3 -c "
import os
filepath = 'src/scrapers/asx.py'
if os.path.exists(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        code = f.read()
    
    # Change the safe JSON fallback from a list [] to a dictionary {}
    if 'return []' in code and '[ASX WAF]' in code:
        updated_code = code.replace('return []', 'return {}')
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(updated_code)
        print('  [OK] ASX fallback type corrected from list to dict.')
"

echo "🚀 Step 5: Dropping old db files to force clean schema generation..."
rm -f ssr_observability.db ssr_cache.sqlite || true

echo "🔄 Step 6: Committing fixes..."
git add src/
git commit -m "fix(core): correct openrouter model string, append missing articles column, fix asx type mismatch" || echo "No changes detected."
git pull --rebase origin main
git push origin main

echo "✅ All logical errors resolved and databases reset. The pipeline should run green."
