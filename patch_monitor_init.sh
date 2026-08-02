#!/bin/bash
set -e

cd ~/special-situations-radar-main

python3 -c "
monitor_path = 'monitor.py'
with open(monitor_path, 'r', encoding='utf-8') as f:
    code = f.read()

# Ensure database initialization is called immediately after imports/startup
target = '=== Special Situations Radar'
init_call = 'from src.database import init_db\ninit_db()\n\n'

if 'init_db()' not in code:
    code = code.replace(target, init_call + target)
    with open(monitor_path, 'w', encoding='utf-8') as f:
        f.write(code)
    print('  [OK] Injected init_db() call into monitor.py startup.')
else:
    print('  [INFO] init_db() already present in monitor.py.')
"

git add monitor.py
git commit -m "fix(db): ensure init_db executes at monitor.py startup" || echo "No changes."
git pull --rebase origin main
git push origin main

echo "✅ Push complete! The tables will now auto-provision on startup."
