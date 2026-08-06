import sqlite3
import json
import os
from datetime import datetime, timezone

db_path = "ssr_observability.db"
if not os.path.exists(db_path):
    print("NOT VERIFIED: ssr_observability.db does not exist locally.")
    exit(0)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("--- PART 1 & 8 DATABASE EVIDENCE ---")
# Get last 50 runs from article_screening_log or workflow_health
cursor.execute("""
    SELECT run_id, COUNT(*) as processed,
           SUM(CASE WHEN outcome = 'PASSED' THEN 1 ELSE 0 END) as passed
    FROM article_screening_log
    GROUP BY run_id
    ORDER BY timestamp DESC
    LIMIT 10
""")
runs = cursor.fetchall()
for r in runs:
    print(f"Run {r['run_id']}: Processed={r['processed']}, Passed={r['passed']}")

print("\n--- PASSED ARTICLES TODAY ---")
cursor.execute("""
    SELECT run_id, timestamp, headline, ticker, event_family
    FROM article_screening_log
    WHERE outcome = 'PASSED'
    ORDER BY timestamp DESC
    LIMIT 20
""")
passed = cursor.fetchall()
for p in passed:
    print(f"[{p['timestamp']}] {p['run_id']} | {p['ticker']} | {p['event_family']} | {p['headline'][:40]}")

print("\n--- AUDIT EVENTS (ERRORS/EXCEPTIONS) ---")
# Check if audit_events table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_events'")
if cursor.fetchone():
    cursor.execute("""
        SELECT timestamp, event_type, severity, details 
        FROM audit_events 
        WHERE event_type LIKE '%EMAIL%' OR event_type LIKE '%SMTP%' OR details LIKE '%email%'
        ORDER BY timestamp DESC LIMIT 20
    """)
    for e in cursor.fetchall():
        print(f"[{e['timestamp']}] {e['severity']}: {e['event_type']} - {e['details']}")
else:
    print("Table audit_events does not exist.")

print("\n--- EXCEPTION LOGS ---")
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='exception_log'")
if cursor.fetchone():
    cursor.execute("""
        SELECT timestamp, stage, error_type, error_message
        FROM exception_log
        ORDER BY timestamp DESC LIMIT 20
    """)
    for e in cursor.fetchall():
        print(f"[{e['timestamp']}] {e['stage']} | {e['error_type']} | {e['error_message']}")

conn.close()
