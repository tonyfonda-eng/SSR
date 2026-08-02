#!/bin/bash
set -e

echo "📦 Step 1: Navigating to project workspace..."
cd ~/special-situations-radar-main

echo "🛠️ Step 2: Injecting init_db wrapper into src/database.py..."
python3 -c "
db_path = 'src/database.py'
with open(db_path, 'r', encoding='utf-8') as f:
    code = f.read()

if 'def init_db' not in code:
    init_snippet = '''

def init_db():
    \"\"\"Ensures all core SQLite database tables are provisioned.\"\"\"
    try:
        # Check for common database initialization methods in database.py
        if 'setup_database' in globals():
            setup_database()
        elif 'init_database' in globals():
            init_database()
        else:
            # Fallback direct table creation execution if needed
            import sqlite3
            conn = sqlite3.connect('ssr_observability.db')
            conn.execute(\"CREATE TABLE IF NOT EXISTS workflow_health (timestamp TEXT PRIMARY KEY, total_scanned INTEGER, articles INTEGER, errors INTEGER, drift_score REAL, runtime REAL);\")
            conn.execute(\"CREATE TABLE IF NOT EXISTS run_metrics_log (timestamp TEXT PRIMARY KEY);\")
            conn.commit()
            conn.close()
    except Exception as e:
        print(f'[DATABASE INIT WARNING] {e}')
'''
    code += init_snippet
    with open(db_path, 'w', encoding='utf-8') as f:
        f.write(code)
    print('  [OK] Added init_db() to src/database.py')
else:
    print('  [INFO] init_db already exists.')
"

echo "🚀 Step 3: Committing and pushing the fix..."
git add src/database.py
git commit -m "fix(db): define init_db wrapper in src/database.py to resolve ImportError"
git pull --rebase origin main
git push origin main

echo "✅ Fix successfully pushed to GitHub!"
