import sqlite3
import sys
import os
from src.validation.coverage_audit import get_prod_db_path, get_dynamic_schema

def trace_missed_opportunity(url_or_ticker):
    prod_db = get_prod_db_path()
    if not os.path.exists(prod_db):
        return "Unknown"

    uri = f"file:{os.path.abspath(prod_db)}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    cursor = conn.cursor()
    
    id_col, url_col, title_col, source_col, has_ticker = get_dynamic_schema(cursor)
    
    if has_ticker:
        cursor.execute(f"SELECT {id_col} FROM articles WHERE {url_col} LIKE ? OR ticker LIKE ? LIMIT 1", 
                       (f"%{url_or_ticker}%", f"%{url_or_ticker}%"))
    else:
        cursor.execute(f"SELECT {id_col} FROM articles WHERE {url_col} LIKE ? LIMIT 1", 
                       (f"%{url_or_ticker}%",))
        
    article = cursor.fetchone()
    if not article:
        conn.close()
        return "Not ingested"
        
    article_id = article[0]
    cursor.execute("SELECT outcome FROM article_lifecycle_log WHERE article_id = ?", (article_id,))
    stages = {row[0] for row in cursor.fetchall()}
    conn.close()

    if 'issuer_duplicate' in stages: return "Duplicate"
    if 'global_exclusion' in stages or 'regex_rejected' in stages: return "Regex"
    if 'ontology_rejected' in stages: return "Ontology"
    if 'rules_rejected' in stages: return "Rules"
    if 'ticker_rejected' in stages: return "Ticker"
    if 'playbook_rejected' in stages or ('ai_classified' in stages and 'email_sent' not in stages and 'alerted' not in stages): return "AI"
    if 'alerted' in stages and 'email_sent' not in stages: return "Email"
    
    return "Unknown"

def batch_update_validation_db(val_db_path="validation.db"):
    if not os.path.exists(val_db_path): return
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
    if len(sys.argv) > 1:
        print(f"\n🔍 TRACE RESULT FOR: {sys.argv[1]}\n🛑 Reason Missed: {trace_missed_opportunity(sys.argv[1])}\n")
    else:
        batch_update_validation_db()
