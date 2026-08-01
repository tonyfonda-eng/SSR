import sqlite3
from pathlib import Path
import datetime

DB_PATH = Path(__file__).resolve().parent.parent / "ssr_cache.sqlite"

import contextlib

@contextlib.contextmanager
def get_connection():    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    try:
        yield conn
    finally:

def initialise_database():    with get_connection() as conn:

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

        conn.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                reminder_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT,
                ticker TEXT,
                reminder_date TEXT,
                message TEXT,
                sent INTEGER DEFAULT 0
            )
        """)

        # 2. Force a schema upgrade if it's loading an old cached database
        try:
            conn.execute("ALTER TABLE articles ADD COLUMN body TEXT")
            print("[DATABASE] Upgraded schema: added 'body' column.")
        except sqlite3.OperationalError:
            pass
            
        try:
            conn.execute("ALTER TABLE reminders ADD COLUMN ticker TEXT")
            print("[DATABASE] Upgraded schema: added 'ticker' column to reminders.")
        except sqlite3.OperationalError:
            pass


        print("[DATABASE] Ready")

def article_exists(article_key):    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM articles WHERE article_key = ?", (article_key,))
        exists = cursor.fetchone() is not None
        return exists

def save_article(source, article_id, title, url, published, body):    with get_connection() as conn:
        cursor = conn.cursor()
        article_key = f"{source}:{article_id}"
        processed_at = datetime.datetime.now().isoformat()
        cursor.execute("""
            INSERT OR REPLACE INTO articles (article_key, source, article_id, title, url, published, body, processed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (article_key, source, article_id, title, url, published, body, processed_at))

def article_count():    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM articles")
        count = cursor.fetchone()[0]
        return count



def track_company(ticker):    with get_connection() as conn:
        cursor = conn.cursor()
        now = datetime.datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO companies (ticker, first_seen, alert_count)
            VALUES (?, ?, 1)
            ON CONFLICT(ticker) DO UPDATE SET alert_count = alert_count + 1
        """, (ticker, now))

def create_event_if_new(event_family, ticker):    """
    Creates an event ID formatted as Ticker_YYYY_MM_DD to enforce a strict 1-alert-per-company-per-day limit.
    Returns (event_id, is_new) where is_new is a boolean.
    """
    now = datetime.datetime.now()
    event_id = f"{ticker}_{now.year}_{now.month:02d}_{now.day:02d}"
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT 1 FROM events WHERE event_id = ?", (event_id,))
        if cursor.fetchone() is not None:
            return event_id, False
            
        cursor.execute("""
            INSERT INTO events (event_id, event_family, target_ticker, status, created_at, updated_at)
            VALUES (?, ?, ?, 'Announced', ?, ?)
        """, (event_id, event_family, ticker, now.isoformat(), now.isoformat()))
        
        return event_id, True

def log_research(event_id, article_id, rules_score, ai_summary):    with get_connection() as conn:
        cursor = conn.cursor()
        now = datetime.datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO research_logs (event_id, article_id, rules_score, ai_summary, processed_at)
            VALUES (?, ?, ?, ?, ?)
        """, (event_id, article_id, rules_score, ai_summary, now))



def save_reminder(event_id, ticker, reminder_date, message):    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO reminders (event_id, ticker, reminder_date, message)
            VALUES (?, ?, ?, ?)
        """, (event_id, ticker, reminder_date, message))

def get_pending_reminders():    with get_connection() as conn:
        cursor = conn.cursor()
        # Find reminders where reminder_date <= today and sent = 0
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        cursor.execute("""
            SELECT reminder_id, event_id, ticker, reminder_date, message 
            FROM reminders 
            WHERE reminder_date <= ? AND sent = 0
        """, (today,))
        reminders = cursor.fetchall()
        return [{'id': r[0], 'event_id': r[1], 'ticker': r[2], 'date': r[3], 'message': r[4]} for r in reminders]

def mark_reminder_sent(reminder_id):    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE reminders SET sent = 1 WHERE reminder_id = ?", (reminder_id,))

