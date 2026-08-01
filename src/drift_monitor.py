import sqlite3
from src.alerts.email import send_alert

def check_pipeline_drift():
    """Compares today's run metrics against 30-day historical averages to flag anomalies and alert via email."""
    print("[DRIFT MONITOR] Analyzing pipeline metrics for statistical drift...")
    conn = sqlite3.connect("ssr_observability.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT articles, runtime, failed 
            FROM workflow_health 
            ORDER BY timestamp DESC 
            LIMIT 1
        """)
        latest = cursor.fetchone()
        
        cursor.execute("""
            SELECT AVG(articles) as avg_articles, AVG(runtime) as avg_runtime 
            FROM workflow_health 
            WHERE timestamp >= datetime('now', '-30 days')
        """)
        baseline = cursor.fetchone()
        
        if not latest or not baseline:
            print("[DRIFT MONITOR] Insufficient historical data for drift calculation.")
            return []

        drift_warnings = []
        latest_articles = latest["articles"] or 0
        avg_articles = baseline["avg_articles"] or 0
        
        # Check for volume crash (>50% drop below 30-day average)
        if avg_articles > 20 and latest_articles < (avg_articles * 0.5):
            drift_warnings.append(f"⚠️ Ingestion volume dropped significantly: Today ({latest_articles}) is >50% below 30-day average ({avg_articles:.1f}).")
            
        # Check for runtime inflation (>2x normal execution time)
        latest_runtime = latest["runtime"] or 0
        avg_runtime = baseline["avg_runtime"] or 0
        if avg_runtime > 0 and latest_runtime > (avg_runtime * 2.0):
            drift_warnings.append(f"⚠️ Pipeline runtime spiked: Current run ({latest_runtime:.1f}s) is double the 30-day baseline ({avg_runtime:.1f}s).")

        if drift_warnings:
            for warning in drift_warnings:
                print(f"[DRIFT DETECTED] {warning}")
            
            # Dispatch immediate email alert for detected anomalies
            summary_text = "\n".join(drift_warnings)
            try:
                send_alert(
                    article_title="SSR Pipeline Drift Alert",
                    article_url="",
                    event_family="DRIFT ALERT",
                    confidence=100,
                    research_summary=f"Automated pipeline telemetry detected structural anomalies during the latest execution:\n\n{summary_text}",
                    evidence_log=[],
                    is_update=False
                )
                print("[DRIFT MONITOR] Drift alert email dispatched successfully.")
            except Exception as email_err:
                print(f"[WARNING] Failed to send drift alert email: {email_err}")
        else:
            print("[DRIFT MONITOR] No structural drift detected. All metrics within normal tolerances.")
            
        return drift_warnings

    except Exception as e:
        print(f"[ERROR] Drift analysis failed: {e}")
        return []
    finally:
        conn.close()

if __name__ == "__main__":
    check_pipeline_drift()