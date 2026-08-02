import sqlite3
import sys
import os
import random
from datetime import datetime
from src.validation.coverage_audit import get_prod_db_path, get_dynamic_schema
from src.validation.tracer import trace_missed_opportunity

def generate_daily_qa_sample(sample_size=100, val_db_path="validation.db"):
    prod_db = get_prod_db_path()
    if not os.path.exists(prod_db):
        print(f"[VQA ERROR] Production cache missing at {prod_db}. Cannot sample.")
        return

    uri = f"file:{os.path.abspath(prod_db)}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    cursor = conn.cursor()
    
    # Dynamically resolve production table architecture
    id_col, url_col, title_col, source_col, has_ticker = get_dynamic_schema(cursor)
    ticker_field = ", ticker" if has_ticker else ""
    
    query = f"SELECT {id_col}, {title_col}, {source_col}, {url_col}{ticker_field} FROM articles ORDER BY {id_col} DESC LIMIT 2000"
    try:
        cursor.execute(query)
        pool = cursor.fetchall()
    except Exception as e:
        print(f"[VQA ERROR] Failed reading pool for sampling: {e}")
        conn.close()
        return
    conn.close()

    if not pool:
        print("[VQA] Ingestion table is empty. No articles to sample.")
        return

    sample = random.sample(pool, min(len(pool), sample_size))
    date_str = datetime.now().strftime("%Y-%m-%d")
    report_path = "docs/DAILY_QA.md"

    print(f"[VQA] Selecting {len(sample)} random articles for human quality control review...")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# Daily QA Sampler (Human Quality Control)\n")
        f.write(f"*Generated: {date_str}*\n\n")
        f.write("⚠️ **CRITICAL ADVISORY BOUNDARY:** This file exists solely for human verification and performance benchmarking. Review entries manually below. Actions performed here are completely read-only and **never** modify production code, live schemas, or downstream alert engines.\n\n")
        f.write("## 🔍 Manual Inspection Sample Matrix\n\n")
        f.write("| # | Ticker | Headline | Source | Pipeline Outcome | Manual Review | Reviewer Notes |\n")
        f.write("|---|--------|----------|--------|------------------|---------------|----------------|\n")

        for idx, row in enumerate(sample, 1):
            if has_ticker:
                art_id, headline, source, url, ticker = row
            else:
                art_id, headline, source, url = row
                ticker = "--"
                
            target = url if url else (ticker if ticker != "--" else str(art_id))
            outcome = trace_missed_opportunity(target)
            if outcome == "Unknown" or "PASSED" in outcome or "alerted" in outcome.lower():
                outcome = "PASSED (Alerted)"

            clean_headline = str(headline).replace("|", "-").strip() if headline else "No Headline"
            clean_url = f"[{source or 'Link'}]({url})" if url else "No URL"

            f.write(f"| {idx} | **{ticker or '--'}** | {clean_headline} | {source or 'Unknown'} | `{outcome}` | [ ] True Pos <br> [ ] True Neg <br> [ ] False Pos <br> [ ] False Neg | |\n")

    print(f"[VQA] Daily sampler compiled successfully to {report_path}")

if __name__ == '__main__':
    generate_daily_qa_sample()
