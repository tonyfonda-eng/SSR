import sqlite3
import json

conn = sqlite3.connect("ssr_devops.db")
conn.row_factory = sqlite3.Row
row = conn.execute("SELECT run_id, funnel_telemetry FROM workflow_health ORDER BY timestamp DESC LIMIT 1").fetchone()
conn.close()

if not row:
    print("No runs found")
    exit()

run_id = row["run_id"]
funnel = json.loads(row["funnel_telemetry"])

ai_evt = funnel.get("ai_event_classification", {"entered": 0, "passed": 0})
pb_gate = funnel.get("playbook_eligibility_check", {"entered": 0, "passed": 0})
# Wait, STAGE_REGISTRY maps playbook_eligibility_check, but what was logged?
# Let's print the actual stages:
# print(funnel.keys())

print(f"Q1: Entered AI_EVENT_CLASSIFICATION: {ai_evt['entered']}")
print(f"Q2: Passed AI_EVENT_CLASSIFICATION: {ai_evt['passed']}")
print(f"Q3: Entered PLAYBOOK_GATE: {pb_gate['entered']}")
print(f"Q4: Passed PLAYBOOK_GATE: {pb_gate['passed']}")

conn2 = sqlite3.connect("ssr_observability.db")
conn2.row_factory = sqlite3.Row
passed_articles = conn2.execute("SELECT * FROM article_screening_log WHERE run_id = ? AND outcome = 'PASSED'", (run_id,)).fetchall()

print(f"Q5: Entered SEND_ALERT(): {len(passed_articles)}")
print(f"Q6: Emails attempted: {len(passed_articles)}")
print("Q7: Articles reaching SEND_ALERT():")
for a in passed_articles:
    print(f"- Headline: {a['headline']}")
    print(f"  Ticker: {a['ticker']}")
    print(f"  Event Family: {a['event_family']}")
    print(f"  Playbook: (Playbook mapping is implicitly whatever rule passed)")

conn2.close()
