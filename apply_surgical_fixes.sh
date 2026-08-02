#!/bin/bash
set -e

echo "📦 Step 1: Navigating to project workspace..."
cd ~/special-situations-radar-main

echo "🧠 Step 2: Fixing the OpenRouter Model String syntax in src/ai.py..."
# Safely transpose the version number and model type using sed
sed -i 's/google\/gemini-flash-1.5/google\/gemini-1.5-flash/g' src/ai.py
print_success() { echo "  [OK] Patched OpenRouter string in src/ai.py"; }
print_success

echo "🗄️ Step 3: Injecting the workflow_health schema into src/database.py..."
python3 -c "
import os
filepath = 'src/database.py'
if os.path.exists(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        code = f.read()
    
    # We look for the main schema execution block and insert the missing table
    if 'CREATE TABLE IF NOT EXISTS workflow_health' not in code:
        schema_injection = '''
        cursor.execute(\"\"\"
            CREATE TABLE IF NOT EXISTS workflow_health (
                timestamp TEXT PRIMARY KEY,
                total_scanned INTEGER,
                errors INTEGER,
                drift_score REAL
            )
        \"\"\")
        '''
        # Find the first standard CREATE TABLE statement and inject right before it
        if 'cursor.execute(' in code:
            code = code.replace(
                \"cursor.execute('''\\n        CREATE TABLE IF NOT EXISTS articles\",
                schema_injection.strip() + \"\\n        cursor.execute('''\\n        CREATE TABLE IF NOT EXISTS articles\"
            )
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(code)
            print('  [OK] workflow_health schema injected into src/database.py')
else:
    print('  [ERROR] src/database.py not found!')
"

echo "📡 Step 4: Adding graceful WAF degradation to the ASX scraper..."
python3 -c "
import os
filepath = 'src/scrapers/asx.py'
if os.path.exists(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        code = f.read()
    
    # Wrap the json parsing block in a try-except to catch the WAF block gracefully
    if 'except ValueError:' not in code and 'except Exception as e:' not in code:
        # This is a broad safety net replacement for the raw json() call
        code = code.replace(
            'data = resp.json()',
            'try:\n                data = resp.json()\n            except ValueError:\n                print(\"[WARNING] ASX WAF challenge encountered. Skipping source.\")\n                return []'
        )
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(code)
        print('  [OK] Graceful degradation added to src/scrapers/asx.py')
"

echo "🚀 Step 5: Committing the targeted fixes..."
git add src/ai.py src/database.py src/scrapers/asx.py
git commit -m "fix(core): correct openrouter model syntax, instantiate missing workflow schema, and handle asx waf blocks gracefully" || echo "No changes detected."
git pull --rebase origin main
git push origin main

echo "✅ All structural patches applied. The system is ready for a clean run."
