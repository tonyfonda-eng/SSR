import sqlite3
import datetime

RESEARCH_DB = "ssr_observability.db"
AUDIT_DB = "ssr_audit.db"

dates = ["2026-08-03", "2026-08-04", "2026-08-05", "2026-08-06", "2026-08-07"]

print("--- AI_APPROVED NOTIFICATION STATS ---")
try:
    conn = sqlite3.connect(RESEARCH_DB)
    c = conn.cursor()
    for d in dates:
        c.execute("SELECT COUNT(*) FROM evaluation_ledger WHERE terminal_stage = 'AI_APPROVED' AND runtime_timestamp LIKE ?", (d + "%",))
        ai_approved = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM article_screening_log WHERE final_stage = 'AI_APPROVED' AND timestamp LIKE ?", (d + "%",))
        screening_approved = c.fetchone()[0]
        
        print(f"{d}: AI_APPROVED (evaluation_ledger): {ai_approved}, AI_APPROVED (article_screening_log): {screening_approved}")
        
        # Are there any records of email successes/failures in the DB? 
        # Check audit_events in ssr_audit.db
        
    conn.close()
    
    print("\n--- AUDIT EVENTS (Email & AI) ---")
    conn = sqlite3.connect(AUDIT_DB)
    c = conn.cursor()
    for d in dates:
        c.execute("SELECT event_type, severity, details, COUNT(*) FROM audit_events WHERE timestamp LIKE ? GROUP BY event_type, severity, details", (d + "%",))
        rows = c.fetchall()
        for r in rows:
            print(f"{d} - {r[0]} ({r[1]}): {r[2]} (Count: {r[3]})")
    conn.close()

except Exception as e:
    print(f"Error querying DBs: {e}")

