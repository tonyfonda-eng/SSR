import sqlite3

conn = sqlite3.connect("ssr_observability.db")
conn.row_factory = sqlite3.Row

# Get latest run_id
run_id = conn.execute("SELECT run_id FROM article_screening_log ORDER BY timestamp DESC LIMIT 1").fetchone()
if not run_id:
    print("No runs found")
    exit()
run_id = run_id[0]
print("Latest run_id:", run_id)

# Count stages
counts = {}
for row in conn.execute("SELECT final_stage, count(*) as c FROM article_screening_log WHERE run_id=? GROUP BY final_stage", (run_id,)):
    counts[row["final_stage"]] = row["c"]

# Since we don't have full funnel_telemetry yet, we can approximate by seeing how many reached each stage.
# For example, anything that drops at playbook_gate must have entered it.
print("Stage drops:", counts)

passed = conn.execute("SELECT * FROM article_screening_log WHERE run_id=? AND outcome='PASSED'", (run_id,)).fetchall()
print("Emails attempted (PASSED articles):", len(passed))
for p in passed:
    print(f"- {p['headline']} | {p['ticker']} | {p['event_family']}")

conn.close()
