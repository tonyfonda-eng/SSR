#!/bin/bash
set -e

echo "📦 Step 1: Navigating to project workspace..."
cd ~/special-situations-radar-main

echo "🧠 Step 2: Removing the invalid -001 suffix from model strings..."
python3 -c "
import os

files_to_fix = ['src/ai.py', 'src/ai_audit_manager.py']
for filepath in files_to_fix:
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            code = f.read()
        
        # Strip out the unsupported -001 suffix
        new_code = code.replace('google/gemini-2.5-flash-001', 'google/gemini-2.5-flash')
        new_code = new_code.replace('google/gemini-2.0-flash-001', 'google/gemini-2.0-flash')
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_code)
        print(f'  [OK] Cleaned model slug in {filepath}')
"

echo "🚀 Step 3: Committing and pushing slug fix..."
git add src/ai.py src/ai_audit_manager.py
git commit -m "fix(ai): remove unsupported -001 suffix from openrouter model slugs"
git pull --rebase origin main
git push origin main

echo "✅ OpenRouter slug successfully corrected and pushed!"
