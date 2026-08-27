import sqlite3
import json
from monitor import stage_public_ticker_gate

db_path = "ssr_observability.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()

# We need rows with text. Does article_screening_log have body text?
c.execute("PRAGMA table_info(article_screening_log)")
columns = [col[1] for col in c.fetchall()]

# The prompt mentions testing on the SSR ingestion corpus.
# Let's see what data is available. If body isn't in article_screening_log, maybe it's in event_registry.
c.execute("PRAGMA table_info(event_registry)")
event_cols = [col[1] for col in c.fetchall()]

print("article_screening_log columns:", columns)
print("event_registry columns:", event_cols)
