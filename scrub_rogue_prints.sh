#!/bin/bash
set -e

echo "📦 Step 1: Navigating to repository..."
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(git -C "$script_dir" rev-parse --show-toplevel)"
cd "$repo_root"

echo "🛠️ Step 2: Scrubbing all malformed indentations..."
python3 -c "
import py_compile
import tempfile
import os

# Read original file
with open('monitor.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Write cleaned content to a temporary file in the same directory
monitor_dir = os.path.dirname(os.path.abspath('monitor.py')) or '.'
fd, temp_path = tempfile.mkstemp(dir=monitor_dir, prefix='.monitor_', suffix='.py.tmp')
try:
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        for line in lines:
            # The rogue injected line starts with exactly 8 spaces. The valid ones have 20.
            if line.startswith('        print(f\"[INGESTION]') and 'fetched' in line:
                print('  [CLEANED] Removed a rogue 8-space indented line.')
                continue
            f.write(line)

    # Validate syntax BEFORE touching the original file
    print('🔍 Step 3: Validating syntax...')
    py_compile.compile(temp_path, doraise=True)
    print('  [SUCCESS] Syntax compilation passed!')

    # Atomically replace the original file only after validation succeeds
    os.replace(temp_path, 'monitor.py')
except Exception as e:
    # Clean up temp file on failure
    if os.path.exists(temp_path):
        os.unlink(temp_path)
    raise
"

echo "🚀 Step 4: Committing and pushing..."

# Check for pre-existing staged changes (fail if any exist)
if git diff --cached --name-only | grep -q .; then
    echo "❌ ERROR: Pre-existing staged changes detected. Aborting to avoid contaminating the automated commit."
    git diff --cached --name-only
    exit 1
fi

# Stage only monitor.py
git add monitor.py

# Only commit if monitor.py actually has staged changes
if git diff --cached --quiet; then
    echo "No changes to commit (monitor.py unchanged)."
else
    git commit -m "fix(syntax): scrub remaining malformed print injection"
fi

branch="$(git symbolic-ref --short HEAD)"
git pull --rebase origin main
git push origin "HEAD:${branch}"

echo "✅ The codebase is scrubbed and the pipeline is clean."
