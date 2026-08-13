import sqlite3
import json

db = "ssr_observability.db"
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row

print("--- article_screening_log stages ---")
for row in conn.execute("SELECT final_stage, count(*) as c FROM article_screening_log GROUP BY final_stage"):
    print(dict(row))

print("\n--- article_screening_log drop_reasons ---")
for row in conn.execute("SELECT drop_reason, count(*) as c FROM article_screening_log GROUP BY drop_reason"):
    print(dict(row))

print("\n--- evaluation_ledger sample ---")
for row in conn.execute("SELECT * FROM evaluation_ledger LIMIT 1"):
    print(dict(row))

print("\n--- devops db workflow_health sample ---")
try:
    dev_conn = sqlite3.connect("ssr_devops.db")
    dev_conn.row_factory = sqlite3.Row
    for row in dev_conn.execute("SELECT * FROM workflow_health ORDER BY timestamp DESC LIMIT 1"):
        d = dict(row)
        if d.get("funnel_telemetry"):
            d["funnel_telemetry"] = d["funnel_telemetry"][:200] + "..."
        print(d)
except Exception as e:
    print("Devops DB error:", e)

