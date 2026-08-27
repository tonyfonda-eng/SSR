import sqlite3
import json
from monitor import _EXCHANGE_REGEX, _LABELS_REGEX, _SUFFIX_REGEX, _BLOOMBERG_REGEX, _CASHTAG_REGEX, _CRYPTO_CASHTAGS, stage_public_ticker_gate

db_path = "ssr_observability.db"  # Assuming articles are stored here or in ssr_devops.db
try:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    # Find a table with articles
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = c.fetchall()
    
    article_table = None
    for t in tables:
        if "article" in t[0].lower() or "event" in t[0].lower() or "log" in t[0].lower():
            article_table = t[0]
            # Try to query
            try:
                c.execute(f"SELECT COUNT(*) FROM {article_table}")
                count = c.fetchone()[0]
                print(f"Table {article_table} has {count} rows")
            except:
                pass
except Exception as e:
    print(e)
