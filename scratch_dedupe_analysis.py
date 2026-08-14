import sqlite3
import json
import hashlib
from datetime import datetime

db_path = 'ssr_observability.db'
try:
    with open('docs/ingestion_ledger.json', 'r') as f:
        ledger = json.load(f)
except Exception as e:
    print(f"Error reading ledger: {e}")
    ledger = []

conn = sqlite3.connect(db_path)
cur = conn.cursor()

print("--- Dedupe Analysis ---")
samples = []
for entry in ledger:
    for art in entry.get("integrity_sample", []):
        source = art.get("source", "").strip().lower()
        title = art.get("title", "").strip().lower()
        art_hash = hashlib.md5(f"{source}::{title}".encode('utf-8')).hexdigest()
        
        cur.execute("SELECT ingest_timestamp FROM event_registry WHERE article_hash = ?", (art_hash,))
        res = cur.fetchone()
        orig_timestamp = res[0] if res else "NOT_FOUND_IN_DB_MIGHT_BE_CACHED_IN_ACTIONS"
        
        if len(samples) < 20:
            samples.append((source, title, art_hash, orig_timestamp))

print("Distribution / Match check for 20 samples:")
for s in samples:
    print(f"Source: {s[0][:20]} | Title: {s[1][:40]} | Hash: {s[2][:8]} | Orig_Time: {s[3]}")

print("-----------------------")
