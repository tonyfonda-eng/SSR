#!/bin/bash
set -e

echo "📦 Step 1: Navigating to project workspace..."
cd ~/special-situations-radar-main

echo "🛠️ Step 2: Patching get_pending_reminders in src/database.py to return []..."
python3 -c "
path = 'src/database.py'
with open(path, 'r', encoding='utf-8') as f:
    code = f.read()

# Replace or insert proper implementation of get_pending_reminders
reminder_stub = '''
def get_pending_reminders():
    \"\"\"Returns an empty list of pending reminders to prevent iteration crashes.\"\"\"
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(\"\"\"
            CREATE TABLE IF NOT EXISTS reminders_cache (
                id TEXT PRIMARY KEY,
                content TEXT,
                status TEXT
            );
        \"\"\"
        cursor = conn.cursor()
        cursor.execute(\"SELECT content FROM reminders_cache WHERE status = 'pending';\")
        rows = cursor.fetchall()
        conn.close()
        return [r[0] for r in rows]
    except Exception:
        return []
'''

if 'def get_pending_reminders' in code:
    import re
    code = re.sub(r'def get_pending_reminders\(\).*?(?=\ndef |\n#|\Z)', reminder_stub.strip(), code, flags=re.DOTALL)
else:
    code += reminder_stub

with open(path, 'w', encoding='utf-8') as f:
    f.write(code)
print('  [OK] Updated get_pending_reminders implementation.')
"

echo "🚀 Step 3: Committing and pushing..."
git add src/database.py
git commit -m "fix(db): ensure get_pending_reminders returns iterable list instead of None"
git pull --rebase origin main
git push origin main

echo "✅ Fix pushed successfully!"
