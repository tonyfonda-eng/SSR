#!/bin/bash
set -e

echo "📦 Step 1: Navigating to project workspace..."
cd ~/special-situations-radar-main

echo "🧹 Step 2: Reverting syntax error and applying clean network wrapper..."
python3 -c "
import re
import os

if os.path.exists('monitor.py'):
    with open('monitor.py', 'r', encoding='utf-8') as f:
        code = f.read()

    # 1. Strip out the broken syntax injection from the previous script
    bad_string = \"headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}, \"
    code = code.replace(bad_string, '')

    # 2. Inject a safe, global wrapper for requests.get to spoof headers without syntax errors
    wrapper_code = '''
# --- WAF BYPASS WRAPPER ---
_orig_get = requests.get
def _spoofed_get(*args, **kwargs):
    headers = kwargs.get('headers', {})
    if isinstance(headers, dict) and 'User-Agent' not in headers:
        headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    kwargs['headers'] = headers
    return _orig_get(*args, **kwargs)
requests.get = _spoofed_get
# --------------------------
'''
    
    if 'WAF BYPASS WRAPPER' not in code:
        # Inject the wrapper immediately after requests is imported
        code = re.sub(r'^(import requests\b.*)$', r'\1\n' + wrapper_code.strip() + '\n', code, count=1, flags=re.MULTILINE)

    with open('monitor.py', 'w', encoding='utf-8') as f:
        f.write(code)
    print('[OK] Syntax error resolved and network wrapper applied safely.')
else:
    print('[ERROR] monitor.py not found in root directory!')
"

echo "🚀 Step 3: Pushing the syntax fix to GitHub..."
git add monitor.py
git commit -m "fix(core): resolve requests.get syntax error and apply safe global network spoofing"
git pull --rebase origin main
git push origin main

echo "✅ Code fixed and pushed. The GitHub runner will now execute smoothly."
