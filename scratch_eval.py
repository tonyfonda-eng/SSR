import sqlite3
import random
from monitor import stage_public_ticker_gate

db_path = "ssr_observability.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("SELECT raw_payload_blob FROM event_registry LIMIT 2000")
rows = c.fetchall()

admitted = 0
rejected = 0
formats = {}
exchanges = {}

false_positives = []
false_negatives = []

for row in rows:
    blob = row[0]
    if not blob: continue
    
    text = blob.decode('utf-8', errors='ignore') if isinstance(blob, bytes) else str(blob)
    
    article = {"body": text, "headline": ""}
    passed, reason = stage_public_ticker_gate(article, {})
    
    if passed:
        admitted += 1
        ticker_type = article.get("_ticker_match_type", "UNKNOWN")
        exchange = article.get("_deterministic_exchange", "UNKNOWN")
        
        formats[ticker_type] = formats.get(ticker_type, 0) + 1
        exchanges[exchange] = exchanges.get(exchange, 0) + 1
    else:
        rejected += 1
        
print("articles admitted:", admitted)
print("articles rejected:", rejected)
print("ticker formats detected:", formats)
print("exchange distribution:", exchanges)

# Look at some failed ones to see if there's a false negative (missed ticker)
# Since we can't manually label thousands, we will just output the stats.
