#!/bin/bash
set -e

echo "📦 Step 1: Navigating to project workspace..."
cd ~/special-situations-radar-main

echo "🛠️ Step 2: Adding article_exists helper to src/database.py..."
python3 -c "
path = 'src/database.py'
with open(path, 'r', encoding='utf-8') as f:
    code = f.read()

if 'def article_exists' not in code:
    helper_code = '''

def article_exists(identifier):
    \"\"\"Checks if an article URL or identifier already exists in SQLite tables.\"\"\"
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table';\")
        tables = [row[0] for row in cursor.fetchall()]
        
        for table in tables:
            c_info = conn.execute(f\"PRAGMA table_info({table})\").fetchall()
            cols = [col[1] for col in c_info]
            for col in cols:
                if col in ('url', 'link', 'article_id', 'id', 'guid'):
                    res = conn.execute(f\"SELECT 1 FROM {table} WHERE {col} = ? LIMIT 1\", (identifier,)).fetchone()
                    if res:
                        conn.close()
                        return True
        conn.close()
    except Exception:
        pass
    return False
'''
    code += helper_code
    with open(path, 'w', encoding='utf-8') as f:
        f.write(code)
    print('  [OK] Added article_exists function.')
else:
    print('  [INFO] article_exists already exists.')
"

echo "🚀 Step 3: Committing and pushing..."
git add src/database.py
git commit -m "fix(db): add article_exists helper function for monitor compatibility"
git pull --rebase origin main
git push origin main

echo "✅ Fix pushed successfully!"
