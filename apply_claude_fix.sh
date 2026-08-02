#!/bin/bash
set -e

echo "📦 Step 1: Navigating to workspace..."
cd ~/special-situations-radar-main

echo "🛠️ Step 2: Writing updated src/database.py with explicit schema migration..."
cat << 'PYTHON_EOF' > src/database.py
import sqlite3
import os
import logging

logger = logging.getLogger(__name__)

DB_PATH = "ssr_observability.db"

def init_db():
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS workflow_health (
            timestamp TEXT PRIMARY KEY,
            run_id TEXT,
            total_scanned INTEGER,
            articles INTEGER,
            errors INTEGER,
            drift_score REAL,
            runtime REAL,
            failed INTEGER DEFAULT 0,
            succeeded INTEGER DEFAULT 0,
            skipped INTEGER DEFAULT 0,
            emails INTEGER DEFAULT 0,
            exception TEXT
        );
    """)
    conn.execute("CREATE TABLE IF NOT EXISTS run_metrics_log (timestamp TEXT PRIMARY KEY);")
    conn.execute("CREATE TABLE IF NOT EXISTS articles_cache (id TEXT PRIMARY KEY, title TEXT, url TEXT, source TEXT, content TEXT, timestamp TEXT);")
    conn.execute("CREATE TABLE IF NOT EXISTS tracked_companies (ticker TEXT PRIMARY KEY, added_at TEXT);")
    conn.execute("CREATE TABLE IF NOT EXISTS events_log (event_id TEXT PRIMARY KEY, event_family TEXT, ticker TEXT, created_at TEXT);")
    conn.execute("CREATE TABLE IF NOT EXISTS reminders_cache (id TEXT PRIMARY KEY, content TEXT, status TEXT);")

    _migrate_workflow_health(conn)  # handles DBs that already existed before this column set

    conn.commit()
    conn.close()
    logger.info("[DATABASE] Fully migrated canonical schema initialized.")

def _migrate_workflow_health(conn):
    """CREATE TABLE IF NOT EXISTS won't touch a table that already exists on disk —
    this adds any columns the current schema needs but an older DB file is missing."""
    required = {
        "run_id": "TEXT",
        "emails": "INTEGER DEFAULT 0",
        "exception": "TEXT",
        "succeeded": "INTEGER DEFAULT 0",
        "failed": "INTEGER DEFAULT 0",
        "skipped": "INTEGER DEFAULT 0",
    }
    existing = {row[1] for row in conn.execute("PRAGMA table_info(workflow_health)")}
    for col, col_type in required.items():
        if col not in existing:
            conn.execute(f"ALTER TABLE workflow_health ADD COLUMN {col} {col_type}")
            logger.info(f"[DATABASE MIGRATION] Added missing column '{col}' to workflow_health.")

initialise_database = init_db

def article_exists(identifier):
    try:
        conn = sqlite3.connect(DB_PATH)
        res = conn.execute("SELECT 1 FROM articles_cache WHERE id = ? OR url = ? LIMIT 1;", (identifier, identifier)).fetchone()
        conn.close()
        return bool(res)
    except Exception:
        return False

def save_article(article_data=None, **kwargs):
    try:
        data = article_data or kwargs
        import datetime
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            INSERT OR REPLACE INTO articles_cache (id, title, url, source, content, timestamp)
            VALUES (?, ?, ?, ?, ?, ?);
        """, (
            data.get('id') or data.get('url') or data.get('link'),
            data.get('title'),
            data.get('url') or data.get('link'),
            data.get('source'),
            data.get('content') or data.get('summary'),
            data.get('timestamp') or datetime.datetime.utcnow().isoformat()
        ))
        conn.commit()
        conn.close()
    except Exception:
        pass

def get_pending_reminders():
    try:
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute("SELECT content FROM reminders_cache WHERE status = 'pending';").fetchall()
        conn.close()
        return [r[0] for r in rows]
    except Exception:
        return []

def log_run(metrics_dict=None):
    import datetime
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("INSERT OR REPLACE INTO run_metrics_log (timestamp) VALUES (?);", (datetime.datetime.utcnow().isoformat(),))
        conn.commit()
        conn.close()
    except Exception:
        pass

def save_workflow_health(health_data=None):
    import datetime
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            INSERT OR REPLACE INTO workflow_health (timestamp, total_scanned, articles, errors, drift_score, runtime, failed, succeeded, skipped, emails, exception)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            datetime.datetime.utcnow().isoformat(),
            health_data.get('total_scanned', 0) if health_data else 0,
            health_data.get('articles', 0) if health_data else 0,
            health_data.get('errors', 0) if health_data else 0,
            health_data.get('drift_score', 0.0) if health_data else 0.0,
            health_data.get('runtime', 0.0) if health_data else 0.0,
            health_data.get('failed', 0) if health_data else 0,
            health_data.get('succeeded', 0) if health_data else 0,
            health_data.get('skipped', 0) if health_data else 0,
            health_data.get('emails', 0) if health_data else 0,
            health_data.get('exception') if health_data else None
        ))
        conn.commit()
        conn.close()
    except Exception:
        pass
PYTHON_EOF

echo "🛠️ Step 3: Writing updated src/sheets_sync.py with resilient schema checking..."
cat << 'PYTHON_EOF' > src/sheets_sync.py
import sqlite3
import logging
from src.config.settings import SHEET_URL

logger = logging.getLogger(__name__)

DB_PATH = "ssr_observability.db"
EXPECTED_COLUMNS = ["run_id", "timestamp", "runtime", "succeeded", "failed", "emails", "articles", "exception"]

def fetch_latest_metrics():
    """Fetches the latest workflow health and run metrics from SQLite safely."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        available = {row[1] for row in cursor.execute("PRAGMA table_info(workflow_health)")}
        columns_to_select = [c for c in EXPECTED_COLUMNS if c in available]

        if not columns_to_select:
            logger.warning("workflow_health has none of the expected columns; skipping sync.")
            conn.close()
            return {}

        query = f"SELECT {', '.join(columns_to_select)} FROM workflow_health ORDER BY timestamp DESC LIMIT 1;"
        row = cursor.execute(query).fetchone()
        conn.close()

        if not row:
            return {}

        metrics = {col: row[col] for col in columns_to_select}
        for col in EXPECTED_COLUMNS:
            metrics.setdefault(col, None)  # older DB versions report None for new fields
        return metrics

    except Exception as e:
        logger.error(f"Failed to fetch latest run metrics from SQLite: {e}")
        return {}

def sync_metrics_to_sheets():
    metrics = fetch_latest_metrics()
    if not metrics:
        print("[WARNING] No run metrics found in database to sync.")
        return
    print(f"[SHEETS SYNC] Successfully fetched metrics: {metrics}")

if __name__ == "__main__":
    sync_metrics_to_sheets()
PYTHON_EOF

echo "⚙️ Step 4: Forcing execution of init_db() to migrate the live database on disk..."
python3 -c "from src.database import init_db; init_db()"

echo "🚀 Step 5: Committing and pushing Claude's architectural fix..."
git add src/database.py src/sheets_sync.py
git commit -m "fix(schema): implement explicit workflow_health migration and resilient sheets_sync fetching"
git pull --rebase origin main
git push origin main

echo "✅ Claude's fix deployed successfully!"
