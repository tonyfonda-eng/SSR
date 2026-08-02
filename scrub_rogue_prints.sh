#!/bin/bash
set -e

echo "📦 Step 1: Navigating to repository..."
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(git -C "$script_dir" rev-parse --show-toplevel)"
cd "$repo_root"

echo "🛠️ Step 2: Scrubbing all malformed indentations..."
python3 -c "
import py_compile

with open('monitor.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

with open('monitor.py', 'w', encoding='utf-8') as f:
    for line in lines:
        # The rogue injected line starts with exactly 8 spaces. The valid ones have 20.
        if line.startswith('        print(f\"[INGESTION]') and 'fetched' in line:
            print('  [CLEANED] Removed a rogue 8-space indented line.')
            continue
        f.write(line)

print('🔍 Step 3: Validating syntax...')
py_compile.compile('monitor.py', doraise=True)
print('  [SUCCESS] Syntax compilation passed!')
"

echo "🚀 Step 4: Committing and pushing..."
git add monitor.py
git commit -m "fix(syntax): scrub remaining malformed print injection" || echo "No changes to commit."
branch="$(git symbolic-ref --short HEAD)"
git pull --rebase origin main
git push origin "HEAD:${branch}"

echo "✅ The codebase is scrubbed and the pipeline is clean."
