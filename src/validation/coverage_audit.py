import sqlite3
import sys
import os
from datetime import datetime

def get_prod_db_path():
    for db_name in ["ssr_cache.sqlite", "radar.db", "data/ssr_cache.sqlite"]:
        if os.path.exists(db_name):
            return db_name
    return "ssr_cache.sqlite"

def get_dynamic_schema(cursor, table_name="articles"):
    """Dynamically identifies column names to prevent schema crashes."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    cols = {row[1] for row in cursor.fetchall()}
    
    id_col = "article_id" if "article_id" in cols else "id"
    url_col = "source_url" if "source_url" in cols else "url"
    title_col = "headline" if "headline" in cols else ("title" if "title" in cols else "'Unknown Title'")
    source_col = "source_name" if "source_name" in cols else ("source" if "source" in cols else "'Unknown Source'")
    has_ticker = "ticker" in cols
    
    return id_col, url_col, title_col, source_col, has_ticker

def audit_event_coverage(url_or_ticker, val_db_path="validation.db"):
    prod_db = get_prod_db_path()
    
    print("\n" + "="*65)
    print(f"         SSR PIPELINE COVERAGE AUDIT")
    print("="*65)
    print(f"Target Identifier : {url_or_ticker}")
    print(f"Production Cache  : {prod_db}")
    print(f"Audit Timestamp   : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 65)

    if not os.path.exists(prod_db):
        print(f"[FAIL] Production cache not found at {prod_db}")
        return "Unknown"

    uri = f"file:{os.path.abspath(prod_db)}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    cursor = conn.cursor()

    # Dynamically resolve columns
    id_col, url_col, title_col, source_col, has_ticker = get_dynamic_schema(cursor)
    
    if has_ticker:
        query = f"SELECT {id_col}, {title_col}, {source_col} FROM articles WHERE {url_col} LIKE ? OR ticker LIKE ? LIMIT 1"
        params = (f"%{url_or_ticker}%", f"%{url_or_ticker}%")
    else:
        query = f"SELECT {id_col}, {title_col}, {source_col} FROM articles WHERE {url_col} LIKE ? LIMIT 1"
        params = (f"%{url_or_ticker}%",)

    cursor.execute(query, params)
    article = cursor.fetchone()

    if not article:
        print(" [FAIL] Stage 1: Ingestion           | Article never fetched by any scraper")
        print("-" * 65)
        print("FINAL RESULT: FAILED\nEXACT ROOT CAUSE: Not ingested\n" + "="*65 + "\n")
        conn.close()
        return "Not ingested"
    
    article_id, headline, source = article
    print(f" [PASS] Stage 1: Ingestion           | ID: {article_id} | Source: {source}")

    cursor.execute("SELECT stage FROM article_lifecycle_log WHERE article_id = ?", (article_id,))
    stages = {row[0] for row in cursor.fetchall()}
    conn.close()

    if 'issuer_duplicate' in stages:
        print(" [FAIL] Stage 2: Deduplication       | Flagged as duplicate issuer filing")
        return finalize_audit("FAILED", "Duplicate")
    print(" [PASS] Stage 2: Deduplication       | Unique filing accepted")

    if 'global_exclusion' in stages or 'regex_rejected' in stages:
        print(" [FAIL] Stage 3: Regex / Exclusions  | Rejected by global keyword/pattern match")
        return finalize_audit("FAILED", "Regex")
    print(" [PASS] Stage 3: Regex / Exclusions  | Passed exclusion filter")

    if 'ontology_rejected' in stages:
        print(" [FAIL] Stage 4: Ontology Engine     | No target corporate action terms matched")
        return finalize_audit("FAILED", "Ontology")
    print(" [PASS] Stage 4: Ontology Engine     | Semantic concepts identified")

    if 'rules_rejected' in stages:
        print(" [FAIL] Stage 5: Rules Engine        | Failed minimum playbook rule thresholds")
        return finalize_audit("FAILED", "Rules")
    print(" [PASS] Stage 5: Rules Engine        | Qualified for rule score thresholds")

    if 'ticker_rejected' in stages:
        print(" [FAIL] Stage 6: Ticker Validation   | Unable to map/verify market ticker")
        return finalize_audit("FAILED", "Ticker")
    print(" [PASS] Stage 6: Ticker Validation   | Ticker successfully verified")

    if 'playbook_rejected' in stages or ('ai_classified' not in stages and 'email_sent' not in stages and 'alerted' not in stages):
        print(" [FAIL] Stage 7: AI Evaluation       | Rejected by AI LLM analysis/playbook")
        return finalize_audit("FAILED", "AI")
    print(" [PASS] Stage 7: AI Evaluation       | Verified as actionable special situation")

    if 'email_sent' in stages or 'alerted' in stages:
        print(" [PASS] Stage 8: Email / Alerting     | Notification successfully dispatched")
        return finalize_audit("PASSED (FULL PIPELINE SUCCESS)", "None (Event alerted)")
    else:
        print(" [FAIL] Stage 8: Email / Alerting     | Passed AI but email dispatch failed")
        return finalize_audit("FAILED", "Email")

def finalize_audit(result_text, root_cause):
    print("-" * 65)
    print(f"FINAL RESULT: {result_text}")
    print(f"EXACT ROOT CAUSE: {root_cause}")
    print("="*65 + "\n")
    return root_cause if "PASSED" not in result_text else "PASSED"

def audit_all_historical_events(val_db_path="validation.db"):
    if not os.path.exists(val_db_path):
        return
    conn = sqlite3.connect(val_db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, company, ticker, announcement_url FROM historical_events")
    events = cursor.fetchall()
    conn.close()

    summary = {}
    for ev_id, company, ticker, url in events:
        target = url if url else ticker
        root_cause = audit_event_coverage(target, val_db_path)
        
        conn = sqlite3.connect(val_db_path)
        c = conn.cursor()
        detected = "Y" if root_cause == "PASSED" else "N"
        c.execute("UPDATE historical_events SET reason_missed = ?, detected_yn = ? WHERE id = ?",
                  (root_cause if root_cause != "PASSED" else "", detected, ev_id))
        conn.commit()
        conn.close()
        
        summary[root_cause] = summary.get(root_cause, 0) + 1

    print("\n" + "="*50 + "\n       COVERAGE AUDIT SUMMARY REPORT\n" + "="*50)
    for cause, count in summary.items():
        print(f"  {cause:<25} : {count:>4}")
    print("="*50 + "\n")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        audit_event_coverage(sys.argv[1])
    else:
        audit_all_historical_events()
