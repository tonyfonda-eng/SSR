import sqlite3
import collections

db_path = 'ssr_observability.db'
try:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT article_hash, event_id FROM event_registry LIMIT 10")
    rows = cur.fetchall()
    print(f"Total rows sampled from event_registry: {len(rows)}")
    print(rows)
    
    cur.execute("SELECT COUNT(*) FROM event_registry")
    print(f"Total rows in event_registry: {cur.fetchone()[0]}")
    
except Exception as e:
    print(f"DB Error: {e}")
