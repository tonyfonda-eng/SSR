import sqlite3
from pathlib import Path
import datetime

DB_PATH = Path(__file__).resolve().parent.parent / "ssr_cache.sqlite"

def get_connection():
    return sqlite3.connect(DB_PATH)

def initialise_database():
    conn = get_connection()

    # 1. Create the table if it is a completely fresh run
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
