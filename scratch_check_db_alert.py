import sqlite3
import json

db_path = "ssr_observability.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()
c.execute("SELECT headline, url, ticker, event_family, outcome, drop_reason FROM article_screening_log WHERE url LIKE '%arrive-logistics%'")
rows = c.fetchall()
print("Matches in screening log:", rows)

c.execute("SELECT headline, url, event_type, target_ticker, detection_outcome, terminal_stage FROM v4_event_ledger WHERE url LIKE '%arrive-logistics%'")
v4_rows = c.fetchall()
print("Matches in v4 ledger:", v4_rows)

