import sqlite3
import json
from monitor import stage_public_ticker_gate

db_path = "ssr_observability.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("SELECT id, body_sha256, drop_reason FROM article_screening_log WHERE drop_reason LIKE '%dropped_entity_error%' OR drop_reason LIKE '%ai_exhausted%' OR drop_reason LIKE '%ai_no_ticker%'")
failed_logs = c.fetchall()

print(f"Total AI Failure/Exhausted/NoTicker events generated historically: {len(failed_logs)}")

c.execute("""
    SELECT l.drop_reason, e.raw_payload_blob 
    FROM article_screening_log l 
    JOIN event_registry e ON l.body_sha256 = e.article_hash 
    WHERE l.drop_reason LIKE '%dropped_entity_error%' OR l.drop_reason LIKE '%ai_exhausted%' OR l.drop_reason LIKE '%ai_no_ticker%'
""")
joined_rows = c.fetchall()

eliminated = 0
for reason, blob in joined_rows:
    if not blob: continue
    text = blob.decode('utf-8', errors='ignore') if isinstance(blob, bytes) else str(blob)
    
    article = {"body": text, "headline": ""}
    passed, _ = stage_public_ticker_gate(article, {})
    
    if not passed:
        eliminated += 1
        
print(f"Total such failures mapped to corpus: {len(joined_rows)}")
print(f"Failures eliminated (rejected before AI) by this gate: {eliminated}")

