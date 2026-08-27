import sqlite3
import json
from monitor import stage_public_ticker_gate

db_path = "ssr_observability.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("SELECT id, body_sha256 FROM article_screening_log WHERE drop_reason LIKE '%Parse Failure%'")
failed_logs = c.fetchall()

print(f"Total AI Failure emails generated historically: {len(failed_logs)}")

# Let's map sha256 to raw_payload_blob if possible
# Since we might not easily map it, let's just see how many of the 2000 random ones failed AI.
# Actually, the user just wants an estimate.
c.execute("""
    SELECT l.drop_reason, e.raw_payload_blob 
    FROM article_screening_log l 
    JOIN event_registry e ON l.body_sha256 = e.article_hash 
    WHERE l.drop_reason LIKE '%Parse Failure%'
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
        
print(f"Total Parse Failures mapped to corpus: {len(joined_rows)}")
print(f"Parse Failures eliminated (rejected before AI) by this gate: {eliminated}")

