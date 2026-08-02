import sqlite3
import os
import logging

logger = logging.getLogger(__name__)
DB_PATH = "ssr_observability.db"

def ensure_columns(conn, table, columns):
    try:
        cursor = conn.execute(f"PRAGMA table_info({table})")
        existing = {row[1] for row in cursor.fetchall()}
        for col_name, col_type in columns.items():
            if col_name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type} DEFAULT 0")
                logger.info(f"[DATABASE MIGRATION] Added missing column '{col_name}' to table '{table}'.")
        conn.commit()
    except Exception as e:
        logger.error(f"[DATABASE MIGRATION ERROR] Failed to update schema for {table}: {e}")

def init_db():
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS workflow_health (timestamp TEXT PRIMARY KEY, total_scanned INTEGER, articles INTEGER, errors INTEGER, drift_score REAL, runtime REAL);")
    conn.execute("CREATE TABLE IF NOT EXISTS run_metrics_log (timestamp TEXT PRIMARY KEY);")
    conn.commit()
    ensure_columns(conn, "workflow_health", {"failed": "INTEGER", "succeeded": "INTEGER", "skipped": "INTEGER"})
    conn.close()

initialise_database = init_db

def article_exists(identifier):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        for table in tables:
            c_info = conn.execute(f"PRAGMA table_info({table})").fetchall()
            cols = [col[1] for col in c_info]
            for col in cols:
                if col in ("url", "link", "article_id", "id", "guid"):
                    res = conn.execute(f"SELECT 1 FROM {table} WHERE {col} = ? LIMIT 1", (identifier,)).fetchone()
                    if res:
                        conn.close()
                        return True
        conn.close()
    except Exception:
        pass
    return False

def save_article(article_data):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("CREATE TABLE IF NOT EXISTS articles_cache (id TEXT PRIMARY KEY, title TEXT, url TEXT, source TEXT, content TEXT, timestamp TEXT);")
        conn.execute("INSERT OR REPLACE INTO articles_cache (id, title, url, source, content, timestamp) VALUES (?, ?, ?, ?, ?, ?);", (
            article_data.get("id") or article_data.get("url"),
            article_data.get("title"),
            article_data.get("url") or article_data.get("link"),
            article_data.get("source"),
            article_data.get("content") or article_data.get("summary"),
            article_data.get("timestamp")
        ))
        conn.commit()
        conn.close()
    except Exception:
        pass

def get_pending_reminders():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("CREATE TABLE IF NOT EXISTS reminders_cache (id TEXT PRIMARY KEY, content TEXT, status TEXT);")
        cursor = conn.cursor()
        cursor.execute("SELECT content FROM reminders_cache WHERE status = 'pending';")
        rows = cursor.fetchall()
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

def __getattr__(name):
    logger.warning(f"[DATABASE WARNING] Stubbing missing legacy import: '{name}'")
    def dummy_stub(*args, **kwargs):
        return None
    return dummy_stub
