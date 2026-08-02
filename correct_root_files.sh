#!/bin/bash
set -e

echo "📦 Step 1: Navigating to project workspace..."
cd ~/special-situations-radar-main

echo "🧠 Step 2: Fixing the OpenRouter Model String in src/ai.py and src/ai_audit_manager.py..."
python3 -c "
import os
files_to_patch = ['src/ai.py', 'src/ai_audit_manager.py']

for path in files_to_patch:
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            code = f.read()
        
        # Replace the broken 2.0-flash string with the stable OpenRouter 1.5-flash endpoint
        updated_code = code.replace('google/gemini-2.0-flash', 'google/gemini-flash-1.5')
        
        if code != updated_code:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(updated_code)
            print(f'[OK] Patched AI model string in {path}')
    else:
        print(f'[⚠️ Warning] Could not find {path}')
"

echo "📡 Step 3: Injecting WAF Bypass into all python files inside src/..."
# Since scrapers could be in multiple files, we apply the safe requests wrapper to all of them
find ./src -type f -name "*.py" -exec python3 -c "
import sys
import re
import os

filepath = sys.argv[1]
with open(filepath, 'r', encoding='utf-8') as f:
    code = f.read()

wrapper_code = '''
# --- WAF BYPASS WRAPPER ---
try:
    import requests
    _orig_get = requests.get
    def _spoofed_get(*args, **kwargs):
        headers = kwargs.get('headers', {})
        if isinstance(headers, dict) and 'User-Agent' not in headers:
            headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        kwargs['headers'] = headers
        return _orig_get(*args, **kwargs)
    requests.get = _spoofed_get
except ImportError:
    pass
# --------------------------
'''
# Only inject if requests is actually used in the file
if 'requests.get' in code and 'WAF BYPASS WRAPPER' not in code:
    code = re.sub(r'^(import requests\b.*)$', r'\1\n' + wrapper_code.strip() + '\n', code, count=1, flags=re.MULTILINE)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(code)
    print(f'[NETWORK FIXED] Injected WAF bypass headers into {filepath}')
" {} \;

echo "🗄️ Step 4: Ensuring database schemas exist globally..."
python3 -c "
import sqlite3
import os

for db_name in ['ssr_cache.sqlite', 'validation.db']:
    try:
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS workflow_health (
                timestamp TEXT PRIMARY KEY,
                total_scanned INTEGER,
                errors INTEGER,
                drift_score REAL
            )
        ''')
        conn.commit()
        conn.close()
        print(f'[OK] Verified workflow_health schema in {db_name}')
    except Exception as e:
        print(f'[ERROR] Failed to initialize {db_name}: {e}')
"

echo "🚀 Step 5: Committing correct patches to GitHub..."
git add src/
git commit -m "fix(core): patch broken AI models in src/ai.py and inject global network WAF bypass"
git pull --rebase origin main
git push origin main

echo "✅ Correct files have been patched and pushed!"
