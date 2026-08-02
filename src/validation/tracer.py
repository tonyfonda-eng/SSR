import sqlite3
import sys
import os
from src.config import SYSTEM_SETTINGS

def trace_missed_opportunity(url_or_ticker):
    """
    Executes a read-only diagnostic waterfall against the production database 
    to determine exactly where a historical event died in the pipeline.
    """
    prod_db = SYSTEM_SETTINGS.get("DATABASE_PATH", "ssr_cache.sqlite")
    
    if not os.path.exists(prod_db):
        print(f"[VQA ERROR] Production cache missing at {prod_db}")
        return

    print(f"\n🔍 TRACING PIPELINE EXECUTION FOR: {url_or_ticker}")
    print("="*60)
    
    # Open read-only connection to production
    uri = f"file:{os.path.abspath(prod_db)}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    cursor = conn.cursor()
    
    # 1. Did SSR ingest it?
    cursor.execute("SELECT id FROM articles WHERE source_url LIKE ? OR ticker LIKE ? LIMIT 1", 
                   (f"%{url_or_ticker}%", f"%{url_or_ticker}%"))
    article = cursor.fetchone()
    
    if not article:
        print("❌ 1. Did SSR ingest it?       -> NO (Failed at Scraper / Not Downloaded)")
        print("="*60)
        conn.close()
        return
        
    article_id = article[0]
    print("✅ 1. Did SSR ingest it?       -> YES")
    
    # Get all lifecycle states for this article
    cursor.execute("SELECT stage FROM article_lifecycle_log WHERE article_id = ?", (article_id,))
    stages = [row[0] for row in cursor.fetchall()]
    
    # 2. Did Regex pass?
    if 'regex_rejected' in stages or 'global_exclusion' in stages:
        print("❌ 2. Did regex pass?          -> NO (Killed by exclusions/regex)")
        print("="*60)
        conn.close()
        return
    print("✅ 2. Did regex pass?          -> YES")
    
    # 3. Did Ontology trigger?
    if 'ontology_rejected' in stages:
        print("❌ 3. Did ontology trigger?    -> NO (No relevant semantic concepts found)")
        print("="*60)
        conn.close()
        return
    print("✅ 3. Did ontology trigger?    -> YES")
    
    # 4. Did Rules trigger?
    if 'rules_rejected' in stages:
        print("❌ 4. Did rules trigger?       -> NO (Did not meet minimum playbook score)")
        print("="*60)
        conn.close()
        return
    print("✅ 4. Did rules trigger?       -> YES")
    
    # 5. Did AI run?
    # Assuming 'ai_classified' or checking ai_usage_log for this article_id
    if 'ai_classified' not in stages and 'playbook_rejected' not in stages and 'email_sent' not in stages:
        print("❌ 5. Did AI run?              -> NO (Failed before or during AI dispatch)")
        print("="*60)
        conn.close()
        return
    print("✅ 5. Did AI run?              -> YES")
    
    # 6. Did email send?
    if 'email_sent' in stages or 'alerted' in stages:
        print("✅ 6. Did email send?          -> YES (System successfully alerted)")
    elif 'playbook_rejected' in stages:
        print("❌ 6. Did email send?          -> NO (AI rejected it during final playbook evaluation)")
    else:
        print("❌ 6. Did email send?          -> NO (Unknown failure post-AI)")

    print("="*60)
    conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m src.validation.tracer <URL_or_Ticker>")
        sys.exit(1)
        
    target = sys.argv[1]
    trace_missed_opportunity(target)
