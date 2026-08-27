import sqlite3
import json

db_path = "ssr_observability.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()
c.execute("SELECT * FROM event_registry WHERE raw_payload_blob LIKE b'%arrive-logistics%'")
rows = c.fetchall()
print("Matches in event_registry:", len(rows))
