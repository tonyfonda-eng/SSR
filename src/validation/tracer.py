import sqlite3
import sys
import os
from src.config import SYSTEM_SETTINGS

# The strict VQA Taxonomy
VALID_REASONS = [
    "Not ingested", "Duplicate", "Regex", "Ontology", 
    "Rules", "Ticker", "AI", "Email", "Unknown"
]

def trace_missed_opportunity(url_or_ticker):
    """
    Executes a read-only waterfall diagnostic and returns 
    a strictly categorized 'Reason Missed'.
    """
    prod_db = SYSTEM_SETTINGS.get("DATABASE_PATH", "ssr_cache.sqlite")
    
    if not os.path.exists(prod_db):
        return "Unknown"

    uri = f"file:{os.path.abspath(prod_db)}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    cursor = conn.cursor()
    
    # 1. Ingestion Check
    cursor.execute("SELECT id FROM articles WHERE source_url LIKE ? OR ticker LIKE ? LIMIT 1", 
                   (f"%{url_or_ticker}%", f"%{url_or_ticker}%"))
    article = cursor.fetchone()
    
    if not article:
        conn.close()
        return "Not ingested"
        
    article_id = article[0]
    
    # Fetch all lifecycle stages achieved
    cursor.execute("SELECT stage FROM article_lifecycle_log WHERE article_id = ?", (article_id,))
    stages = {row[0] for row in cursor.fetchall()}
    conn.close()

    # 2-9. Waterfall Taxonomy Resolution
    if 'issuer_duplicate' in stages:
        return "Duplicate"
    elif 'global_exclusion' in stages or 'regex_rejected' in stages:
        return "Regex"
    elif 'ontology_rejected' in stages:
        return "Ontology"
    elif 'rules_rejected' in stages:
        return "Rules"
    elif 'ticker_rejected' in stages:
        return "Ticker"
    elif 'playbook_rejected' in stages or ('ai_classified' in stages and 'email_sent' not in stages and 'alerted' not in stages):
        return "AI"
    elif 'alerted' in stages and 'email_sent' not in stages:
        return "Email"
    
    return "Unknown"

def batch_update_validation_db(val_db_path="validation.db"):
    """
    Scans the validation database for any records missing a 'Reason Missed'
    and automatically classifies them using the Traceability Engine.
    """
    if not os.path.exists(val_db_path):
        print(f"[VQA ERROR] {val_db_path} not found.")
        return

    conn = sqlite3.connect(val_db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, announcement_url, ticker FROM historical_events WHERE reason_missed = '' OR reason_missed IS NULL")
    unclassified = cursor.fetchall()
    
    if not unclassified:
        print("[VQA] All historical events are fully classified.")
        conn.close()
        return

    print(f"\n[VQA] Classifying {len(unclassified)} historical events...")
    
    for row_id, url, ticker in unclassified:
        target = url if url else ticker
        reason = trace_missed_opportunity(target)
        
        print(f"  ID {row_id} | {target[:40]:<40} -> {reason}")
        
        cursor.execute("UPDATE historical_events SET reason_missed = ? WHERE id = ?", (reason, row_id))
        
    conn.commit()
    conn.close()
    print("[VQA] Batch classification complete.")

if __name__ == "__main__":
    # If passed an argument, trace that specific URL/Ticker. Otherwise, run the batch updater.
    if len(sys.argv) > 1:
        target_val = sys.argv[1]
        reason = trace_missed_opportunity(target_val)
        print(f"\n🔍 TRACE RESULT FOR: {target_val}")
        print(f"🛑 Reason Missed: {reason}\n")
    else:
        batch_update_validation_db()
