import sqlite3
import datetime
from src.alerts.email import send_alert

def generate_weekly_qa_report():
    """Compiles a weekly institutional QA report from SQLite metrics and sends an email summary."""
    print("[WEEKLY QA] Compiling weekly operational telemetry and performance summary...")
    conn = sqlite3.connect("ssr_observability.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # 1. Fetch 7-day workflow health summary
        cursor.execute("""
            SELECT 
                COUNT(*) as total_runs,
                SUM(success) as successful_runs,
                SUM(failed) as failed_runs,
                AVG(runtime) as avg_runtime,
                SUM(articles) as total_articles,
                SUM(emails) as total_emails
            FROM workflow_health
            WHERE timestamp >= datetime('now', '-7 days')
        """)
        health_summary = cursor.fetchone()
        
        # 2. Fetch source performance breakdown over the last 7 days
        cursor.execute("""
            SELECT source_name, SUM(downloaded) as downloaded, SUM(alerts) as alerts
            FROM source_stats
            WHERE timestamp >= datetime('now', '-7 days')
            GROUP BY source_name
            ORDER BY downloaded DESC
        """)
        sources = cursor.fetchall()
        
        # 3. Fetch recent exception counts
        cursor.execute("""
            SELECT exc_type, COUNT(*) as count
            FROM exception_log
            WHERE timestamp >= datetime('now', '-7 days')
            GROUP BY exc_type
            ORDER BY count DESC
        """)
        exceptions = cursor.fetchall()

        total_runs = health_summary["total_runs"] or 0
        if total_runs == 0:
            print("[WEEKLY QA] No execution records found for the past 7 days.")
            return

        success_rate = (health_summary["successful_runs"] / total_runs) * 100
        total_articles = health_summary["total_articles"] or 0
        total_emails = health_summary["total_emails"] or 0
        signal_efficiency = (total_emails / max(1, total_articles)) * 100

        # Build report body
        report_lines = [
            "=== SPECIAL SITUATIONS RADAR: WEEKLY MANAGEMENT QA ===",
            f"Report Window: Past 7 Days ({datetime.datetime.utcnow().strftime('%Y-%m-%d')})",
            "",
            "--- SYSTEM VITALITY ---",
            f"• Total Pipeline Runs: {total_runs}",
            f"• Success Rate: {success_rate:.1f}% ({health_summary['successful_runs']} successful, {health_summary['failed_runs']} failed)",
            f"• Average Runtime: {health_summary['avg_runtime']:.1f}s",
            f"• Total Articles Ingested: {total_articles:,}",
            f"• Total Actionable Alerts: {total_emails}",
            f"• Signal Efficiency: {signal_efficiency:.3f}%",
            "",
            "--- TOP SOURCE VOLUMES ---"
        ]

        for src in sources[:5]:
            report_lines.append(f"• {src['source_name']}: {src['downloaded']:,} downloaded, {src['alerts']} alerts")

        if exceptions:
            report_lines.append("")
            report_lines.append("--- RECORDED EXCEPTIONS ---")
            for exc in exceptions:
                report_lines.append(f"• {exc['exc_type']}: {exc['count']} occurrence(s)")

        report_body = "\n".join(report_lines)
        print(report_body)

        # Dispatch Weekly QA email report
        send_alert(
            article_title="SSR Weekly Management QA Report",
            article_url="",
            event_family="WEEKLY QA",
            confidence=100,
            research_summary=report_body,
            evidence_log=[],
            is_update=False
        )
        print("[WEEKLY QA] Weekly QA summary email dispatched successfully.")

    except Exception as e:
        print(f"[ERROR] Weekly QA report generation failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    generate_weekly_qa_report()