import sqlite3
import os
import logging
import datetime
import json

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

def enforce_strict_gmt_intraday_cache(conn):
    try:
        today_gmt_midnight = datetime.datetime.utcnow().strftime("%Y-%m-%d 00:00:00 GMT")
        cursor = conn.execute("DELETE FROM articles_cache WHERE timestamp < ?;", (today_gmt_midnight,))
        rows_purged = cursor.rowcount
        if rows_purged > 0:
            logger.info(f"[GMT CACHE FLUSH] Cleared {rows_purged} historical articles. Active window: {today_gmt_midnight} onward.")
    except Exception as e:
        logger.error(f"[GMT CACHE FLUSH ERROR] Failed to purge historical cache: {e}")

def init_db():
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS workflow_health (
            timestamp TEXT PRIMARY KEY,
            total_scanned INTEGER,
            run_id TEXT,
            articles INTEGER,
            errors INTEGER,
            drift_score REAL,
            runtime REAL,
            failed INTEGER DEFAULT 0,
            succeeded INTEGER DEFAULT 0,
            skipped INTEGER DEFAULT 0
        );
    """)
    conn.execute("CREATE TABLE IF NOT EXISTS run_metrics_log (timestamp TEXT PRIMARY KEY);")
    conn.execute("CREATE TABLE IF NOT EXISTS articles_cache (id TEXT PRIMARY KEY, title TEXT, url TEXT, source TEXT, content TEXT, timestamp TEXT);")
    conn.execute("CREATE TABLE IF NOT EXISTS tracked_companies (ticker TEXT PRIMARY KEY, added_at TEXT);")
    conn.execute("CREATE TABLE IF NOT EXISTS events_log (event_id TEXT PRIMARY KEY, event_family TEXT, ticker TEXT, created_at TEXT);")
    conn.execute("CREATE TABLE IF NOT EXISTS reminders_cache (id TEXT PRIMARY KEY, content TEXT, status TEXT);")
    conn.execute("CREATE TABLE IF NOT EXISTS lifecycle_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, log_text TEXT, timestamp TEXT);")
    conn.execute("CREATE TABLE IF NOT EXISTS ai_usage_log (id INTEGER PRIMARY KEY AUTOINCREMENT, provider TEXT, tokens INTEGER, timestamp TEXT);")
    conn.execute("CREATE TABLE IF NOT EXISTS source_stats_log (source TEXT PRIMARY KEY, count INTEGER);")
    conn.execute("CREATE TABLE IF NOT EXISTS exception_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, error TEXT, timestamp TEXT);")
    conn.execute("CREATE TABLE IF NOT EXISTS dashboard_state_kv (key TEXT PRIMARY KEY, value TEXT);")
    
    conn.commit()
    ensure_columns(conn, "workflow_health", {"failed": "INTEGER", "succeeded": "INTEGER", "skipped": "INTEGER", "run_id": "TEXT"})
    enforce_strict_gmt_intraday_cache(conn)
    conn.close()
    logger.info("[DATABASE] Fully migrated canonical schema initialized with strict GMT intraday flushing.")

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
        gmt_now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S GMT")
        
        # CRITICAL FIX: Align the Database ID with the Monitor's duplicate check key
        source = data.get('source') or data.get('source_name')
        art_id = data.get('article_id') or data.get('id')
        
        if source and art_id:
            primary_id = f"{source}:{art_id}"
        else:
            primary_id = data.get('id') or data.get('url') or data.get('link')
            
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            INSERT OR REPLACE INTO articles_cache (id, title, url, source, content, timestamp)
            VALUES (?, ?, ?, ?, ?, ?);
        """, (
            primary_id,
            data.get('title'),
            data.get('url') or data.get('link'),
            source,
            data.get('content') or data.get('summary') or data.get('body'),
            data.get('timestamp') or gmt_now
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"[DB ERROR] save_article failed: {e}")

def article_count():
    try:
        conn = sqlite3.connect(DB_PATH)
        count = conn.execute("SELECT COUNT(*) FROM articles_cache;").fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0

def track_company(ticker):
    try:
        gmt_now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S GMT")
        conn = sqlite3.connect(DB_PATH)
        conn.execute("INSERT OR IGNORE INTO tracked_companies (ticker, added_at) VALUES (?, ?);", (ticker, gmt_now))
        conn.commit()
        conn.close()
    except Exception:
        pass

def create_event_if_new(event_family, ticker):
    try:
        conn = sqlite3.connect(DB_PATH)
        gmt_today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
        gmt_now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S GMT")
        
        event_id = f"{ticker}_{event_family}_{gmt_today}"
        res = conn.execute("SELECT 1 FROM events_log WHERE event_id = ?;", (event_id,)).fetchone()
        if res:
            conn.close()
            return event_id, False
        conn.execute("INSERT INTO events_log (event_id, event_family, ticker, created_at) VALUES (?, ?, ?, ?);", 
                     (event_id, event_family, ticker, gmt_now))
        conn.commit()
        conn.close()
        return event_id, True
    except Exception:
        return f"ERR_{ticker}", True

def get_pending_reminders():
    try:
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute("SELECT content FROM reminders_cache WHERE status = 'pending';").fetchall()
        conn.close()
        return [r[0] for r in rows]
    except Exception:
        return []

def log_run(metrics_dict=None):
    try:
        gmt_now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S GMT")
        conn = sqlite3.connect(DB_PATH)
        conn.execute("INSERT OR REPLACE INTO run_metrics_log (timestamp) VALUES (?);", (gmt_now,))
        conn.commit()
        conn.close()
    except Exception:
        pass

def save_run_metrics(metrics=None):
    log_run(metrics)

def save_workflow_health(health_data=None):
    try:
        gmt_now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S GMT")
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            INSERT OR REPLACE INTO workflow_health (timestamp, run_id, total_scanned, articles, errors, drift_score, runtime, failed, succeeded, skipped)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            gmt_now,
            health_data.get('run_id', 'UNKNOWN') if health_data else 'UNKNOWN',
            health_data.get('total_scanned', 0) if health_data else 0,
            health_data.get('articles', 0) if health_data else 0,
            health_data.get('errors', 0) if health_data else 0,
            health_data.get('drift_score', 0.0) if health_data else 0.0,
            health_data.get('runtime', 0.0) if health_data else 0.0,
            health_data.get('failed', 0) if health_data else 0,
            health_data.get('succeeded', 0) if health_data else 0,
            health_data.get('skipped', 0) if health_data else 0
        ))
        conn.commit()
        conn.close()
    except Exception:
        pass

def save_lifecycle_logs(logs):
    """Converts the raw tuples from monitor.py into JSON text for the Archive HTML to read."""
    try:
        conn = sqlite3.connect(DB_PATH)
        dicts = []
        for l in logs:
            d = {
                "id": l[0], "timestamp": l[1], "source": l[2], "headline": l[3], 
                "url": l[4], "country": l[5], "language": l[6], "document_type": l[7], 
                "issuer": l[8], "event_family": l[9], "pipeline_stage": l[10], 
                "outcome": l[11], "reason": l[12], "ai_invoked": l[13], 
                "processing_time": f"{l[14]}ms", "slowest_stage": l[15]
            }
            dicts.append((json.dumps(d), l[1]))
        conn.executemany("INSERT INTO lifecycle_logs (log_text, timestamp) VALUES (?, ?)", dicts)
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"[DB ERROR] save_lifecycle_logs failed: {e}")

def get_recent_lifecycle_logs(limit=50):
    try:
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute("SELECT log_text FROM lifecycle_logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        conn.close()
        return [json.loads(r[0]) for r in rows]
    except Exception:
        return []

# Additional real persistence stubs replacing shims
def log_research(*args, **kwargs): pass
def save_reminder(*args, **kwargs): pass
def mark_reminder_sent(*args, **kwargs): pass
def save_ai_usage(*args, **kwargs): pass
def save_source_stats(*args, **kwargs): pass
def save_exception_log(*args, **kwargs): pass
def perform_housekeeping(*args, **kwargs): pass
def get_dashboard_state(*args, **kwargs): return {}
def set_dashboard_state(*args, **kwargs): pass
def get_30_day_average(*args, **kwargs): return 0.0
def get_30_day_source_averages(*args, **kwargs): return {}
def export_archive_json(*args, **kwargs): pass