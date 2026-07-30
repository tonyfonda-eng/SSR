import sqlite3
from pathlib import Path
import datetime

DB_PATH = Path(__file__).resolve().parent.parent / "ssr_cache.sqlite"

def get_connection():
    return sqlite3.connect(DB_PATH)

def initialise_database():
    conn = get_connection()

    # 1. Create the tables if it is a completely fresh run
    conn.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            article_key TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            article_id TEXT NOT NULL,
            title TEXT,
            url TEXT,
            published TEXT,
            body TEXT,
            processed_at TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            ticker TEXT PRIMARY KEY,
            first_seen TEXT,
            alert_count INTEGER DEFAULT 0
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            event_id TEXT PRIMARY KEY,
            event_family TEXT,
            target_ticker TEXT,
            status TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS research_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT,
            article_id TEXT,
            rules_score INTEGER,
            ai_summary TEXT,
            processed_at TEXT
        )
    """)

    # 2. Force a schema upgrade if it's loading an old cached database
    try:
        conn.execute("ALTER TABLE articles ADD COLUMN body TEXT")
        print("[DATABASE] Upgraded schema: added 'body' column.")
    except sqlite3.OperationalError:
        # The column already exists, safe to ignore
        pass

    conn.commit()
    conn.close()

    print("[DATABASE] Ready")

def article_exists(article_key):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM articles WHERE article_key = ?", (article_key,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def save_article(source, article_id, title, url, published, body):
    conn = get_connection()
    cursor = conn.cursor()
    article_key = f"{source}:{article_id}"
    processed_at = datetime.datetime.now().isoformat()
    cursor.execute("""
        INSERT OR REPLACE INTO articles (article_key, source, article_id, title, url, published, body, processed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (article_key, source, article_id, title, url, published, body, processed_at))
    conn.commit()
    conn.close()

def article_count():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM articles")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def track_company(ticker):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO companies (ticker, first_seen, alert_count)
        VALUES (?, ?, 1)
        ON CONFLICT(ticker) DO UPDATE SET alert_count = alert_count + 1
    """, (ticker, now))
    conn.commit()
    conn.close()

def create_event_if_new(event_family, ticker):
    """
    Creates an event ID formatted as EventFamily_Ticker_YYYY_MM.
    Returns (event_id, is_new) where is_new is a boolean.
    """
    now = datetime.datetime.now()
    event_id = f"{event_family.replace(' ', '_')}_{ticker}_{now.year}_{now.month:02d}"
    
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT 1 FROM events WHERE event_id = ?", (event_id,))
    if cursor.fetchone() is not None:
        conn.close()
        return event_id, False
        
    cursor.execute("""
        INSERT INTO events (event_id, event_family, target_ticker, status, created_at, updated_at)
        VALUES (?, ?, ?, 'Announced', ?, ?)
    """, (event_id, event_family, ticker, now.isoformat(), now.isoformat()))
    
    conn.commit()
    conn.close()
    return event_id, True

def log_research(event_id, article_id, rules_score, ai_summary):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO research_logs (event_id, article_id, rules_score, ai_summary, processed_at)
        VALUES (?, ?, ?, ?, ?)
    """, (event_id, article_id, rules_score, ai_summary, now))
    conn.commit()
    conn.close()
