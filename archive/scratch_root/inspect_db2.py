import sqlite3
import json

db = "ssr_devops.db"
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row

print("\n--- devops db workflow_health sample ---")
for row in conn.execute("SELECT run_id, funnel_telemetry FROM workflow_health ORDER BY timestamp DESC LIMIT 10"):
    d = dict(row)
    if d.get("funnel_telemetry") and len(d["funnel_telemetry"]) > 10:
        telemetry = json.loads(d["funnel_telemetry"])
        print(d["run_id"], "stages:", list(telemetry.keys()))
        print("Example stage 'dedupe_hash':", telemetry.get("dedupe_hash"))
        break
    else:
        print(d["run_id"], "No funnel telemetry")

