import sqlite3

db_path = "ssr_observability.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()
c.execute("SELECT timestamp, outcome, final_stage, drop_reason, ticker, event_family FROM article_screening_log WHERE url LIKE '%arrive%' OR url LIKE '%mubadala%' OR headline LIKE '%arrive%' OR headline LIKE '%mubadala%'")
rows = c.fetchall()
for row in rows:
    print(row)
