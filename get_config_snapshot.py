import sqlite3
import json

conn = sqlite3.connect("ssr_observability.db")
conn.row_factory = sqlite3.Row
cursor = conn.cursor()
cursor.execute("SELECT config_json FROM config_snapshots ORDER BY captured_at DESC LIMIT 1")
row = cursor.fetchone()
if row:
    cfg = json.loads(row["config_json"])
    print("PLAYBOOKS:", json.dumps(cfg.get("playbooks", []), indent=2))
