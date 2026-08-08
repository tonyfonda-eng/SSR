import sqlite3
import csv
import datetime
import os
import sys

def export_daily_report(date_str=None):
    if not date_str:
        date_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        
    db_path = "ssr_observability.db"
    out_path = f"docs/ingestion_report_{date_str}.csv"
    
    if not os.path.exists(db_path):
        print(f"Database {db_path} not found. Has the pipeline run yet?")
        return
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT timestamp, source, ingestion_mode, headline, url, outcome, final_stage, drop_reason
        FROM article_screening_log
        WHERE substr(timestamp, 1, 10) = ?
        ORDER BY timestamp ASC
    """, (date_str,))
    
    rows = cursor.fetchall()
    
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Timestamp", "Source", "Channel", "Headline", "URL", "Outcome", "Stage", "Reason"])
        writer.writerows(rows)
        
    print(f"[EXPORT SUCCESS] Generated end-of-day report: {out_path}")
    print(f"[METRICS] Total Articles Scanned Today: {len(rows)}")
    
    # Quick Summary
    cursor.execute("""
        SELECT outcome, COUNT(*) 
        FROM article_screening_log 
        WHERE substr(timestamp, 1, 10) = ? 
        GROUP BY outcome
    """, (date_str,))
    summary = cursor.fetchall()
    for outcome, count in summary:
        print(f"          - {outcome.upper()}: {count}")
        
    conn.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        export_daily_report(sys.argv[1])
    else:
        export_daily_report()
