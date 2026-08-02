#!/bin/bash
set -e

echo "📦 Step 1: Navigating to project workspace..."
cd ~/special-situations-radar-main

echo "🧠 Step 2: Aligning src/ai.py model slug to google/gemini-2.5-flash..."
python3 -c "
import os
ai_file = 'src/ai.py'
if os.path.exists(ai_file):
    with open(ai_file, 'r', encoding='utf-8') as f:
        code = f.read()
    
    # Harmonize with the verified model slug from test_ai_keys.yml
    code = code.replace('google/gemini-2.0-flash-001', 'google/gemini-2.5-flash')
    code = code.replace('google/gemini-2.0-flash', 'google/gemini-2.5-flash')
    
    with open(ai_file, 'w', encoding='utf-8') as f:
        f.write(code)
    print('  [OK] Model slug updated to google/gemini-2.5-flash in src/ai.py')
"

echo "🛠️ Step 3: Adding git pull rebase safety to the workflow commit step..."
python3 -c "
import glob

# Find the main workflow file containing the dashboard commit step
workflow_files = glob.glob('.github/workflows/*.yml')
for wf in workflow_files:
    with open(wf, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if 'docs/index.html' in content and 'git pull' not in content:
        # Inject git pull before git add
        target = 'git add docs/index.html'
        replacement = 'git pull origin main --rebase || true\n          git add docs/index.html'
        new_content = content.replace(target, replacement)
        
        with open(wf, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f'  [OK] Added git pull rebase protection to {wf}')
"

echo "🚀 Step 4: Committing and pushing workflow and model fixes..."
git add src/ai.py .github/workflows/
git commit -m "fix(core): align openrouter model to gemini-2.5-flash and add workflow rebase protection" || echo "No changes to commit."
git pull --rebase origin main
git push origin main

echo "✅ All updates successfully applied and pushed to GitHub!"
