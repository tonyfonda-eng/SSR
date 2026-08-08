import sqlite3
import datetime

RESEARCH_DB = "ssr_observability.db"
DEVOPS_DB = "ssr_devops.db"
AUDIT_DB = "ssr_audit.db"

dates = ["2026-08-03", "2026-08-04", "2026-08-05", "2026-08-06", "2026-08-07"]

print("Date | Raw | Unique | Dedupe Passed | Dedupe Rejected | Ontology Passed | AI Reached | AI Passed | Alerts | Email Att. | Email Sent")
for d in dates:
    print(f"--- {d} ---")
    
    # from DevOps DB - workflow_health
    try:
        conn = sqlite3.connect(DEVOPS_DB)
        c = conn.cursor()
        c.execute("SELECT SUM(total_scanned), SUM(articles) FROM workflow_health WHERE timestamp LIKE ?", (d + "%",))
        row = c.fetchone()
        raw = row[0] if row[0] else "UNKNOWN"
        unique = row[1] if row[1] else "UNKNOWN"
        conn.close()
    except Exception as e:
        raw = unique = f"ERR {e}"
        
    # from Research DB - evaluation_ledger and article_screening_log
    try:
        conn = sqlite3.connect(RESEARCH_DB)
        c = conn.cursor()
        
        # Dedupe passed = articles that reached the next stage after dedupe_hash
        c.execute("SELECT COUNT(*) FROM article_screening_log WHERE timestamp LIKE ? AND (final_stage != 'dedupe_hash' OR outcome = 'PASSED')", (d + "%",))
        dedupe_passed = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM article_screening_log WHERE timestamp LIKE ? AND final_stage = 'dedupe_hash' AND outcome = 'DROPPED'", (d + "%",))
        dedupe_rejected = c.fetchone()[0]
        
        # Ontology passed: didn't drop at ontology_concepts
        # Wait, if they dropped after ontology, they reached regex_rules etc.
        # So ontology passed = total passed dedupe - dropped at ontology
        c.execute("SELECT COUNT(*) FROM article_screening_log WHERE timestamp LIKE ? AND final_stage = 'ontology_concepts' AND outcome = 'DROPPED'", (d + "%",))
        ontology_dropped = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM article_screening_log WHERE timestamp LIKE ? AND final_stage IN ('ai_ticker_resolution', 'ai_event_classification') AND outcome = 'DROPPED' AND drop_reason = 'ai_exhausted'", (d + "%",))
        ai_exhausted = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM article_screening_log WHERE timestamp LIKE ? AND final_stage = 'AI_APPROVED' AND outcome = 'PASSED'", (d + "%",))
        alerts = c.fetchone()[0]
        
        conn.close()
    except Exception as e:
        dedupe_passed = dedupe_rejected = ontology_dropped = alerts = ai_exhausted = f"ERR {e}"
        
    print(f"Raw: {raw}, Unique: {unique}")
    print(f"Dedupe Passed: {dedupe_passed}, Dedupe Rejected: {dedupe_rejected}")
    print(f"Ontology Dropped: {ontology_dropped}")
    print(f"AI Exhausted: {ai_exhausted}, Alerts (AI_APPROVED): {alerts}")

