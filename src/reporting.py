import sqlite3
import datetime
from pathlib import Path
from src.database import DB_PATH

def generate_weekly_report(output_dir="docs"):
    """Generates an automated weekly markdown report of pipeline operations."""
    
    print("[REPORTING] Generating Weekly Operations Report...")
    
    end_date = datetime.datetime.utcnow()
    start_date = end_date - datetime.timedelta(days=7)
    
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # 1. Pipeline Metrics Aggregation
        cursor.execute("""
            SELECT 
                SUM(downloaded) as total_dl,
                SUM(reached_ai) as total_ai,
                SUM(emails_sent) as total_alerts,
                AVG(total_runtime_s) as avg_runtime
            FROM run_metrics_log
            WHERE date(timestamp) >= ? AND date(timestamp) <= ?
        """, (start_str, end_str))
        pipeline = cursor.fetchone()
        
        total_dl = pipeline["total_dl"] or 0
        total_ai = pipeline["total_ai"] or 0
        total_alerts = pipeline["total_alerts"] or 0
        avg_runtime = pipeline["avg_runtime"] or 0.0
        
        # 2. Source Quality Aggregation
        cursor.execute("""
            SELECT 
                source,
                SUM(downloaded) as volume,
                SUM(alerts) as alerts,
                AVG(processing_time_sum / NULLIF(processed_count, 0)) as avg_latency
            FROM source_stats_log
            WHERE date(timestamp) >= ? AND date(timestamp) <= ?
            GROUP BY source
            ORDER BY alerts DESC, volume DESC
        """, (start_str, end_str))
        sources = cursor.fetchall()
        
        # 3. AI Usage Aggregation
        cursor.execute("""
            SELECT 
                provider,
                SUM(requests) as reqs,
                SUM(success) as successes,
                SUM(errors_429) as rate_limits,
                MAX(max_latency) as peak_latency
            FROM ai_usage_log
            WHERE date(timestamp) >= ? AND date(timestamp) <= ?
            GROUP BY provider
        """, (start_str, end_str))
        ai_usage = cursor.fetchall()
        
        # 4. Event & Playbook Aggregation (Event Architecture Prep)
        cursor.execute("""
            SELECT 
                event_family,
                COUNT(log_id) as alert_count
            FROM article_lifecycle_log
            WHERE date(timestamp) >= ? AND date(timestamp) <= ?
            AND outcome LIKE '%Alert Sent%'
            GROUP BY event_family
            ORDER BY alert_count DESC
        """, (start_str, end_str))
        events = cursor.fetchall()

        # Build Markdown Report
        md = f"# SSR Weekly Operations Report\n\n"
        md += f"**Reporting Period:** {start_str} to {end_str}\n"
        md += f"**Generated At:** {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
        
        md += "## 1. Pipeline Summary\n"
        md += f"- **Articles Downloaded:** {total_dl:,}\n"
        md += f"- **Articles Reaching AI:** {total_ai:,}\n"
        md += f"- **Total Alerts Produced:** {total_alerts:,}\n"
        md += f"- **Overall Signal Rate:** {(total_alerts / total_dl * 100) if total_dl > 0 else 0:.2f}%\n"
        md += f"- **Average Pipeline Runtime:** {avg_runtime:.2f}s\n\n"
        
        md += "## 2. Source Performance\n"
        md += "| Source | Volume | Alerts | Signal Rate | Avg Latency |\n"
        md += "|---|---|---|---|---|\n"
        
        worst_sources = []
        for src in sources:
            vol = src["volume"]
            al = src["alerts"]
            sig_rate = (al / vol * 100) if vol > 0 else 0
            md += f"| {src['source']} | {vol:,} | {al:,} | {sig_rate:.2f}% | {src['avg_latency'] or 0:.0f}ms |\n"
            if vol > 50 and al == 0:
                worst_sources.append(src['source'])
        md += "\n"
        
        md += "## 3. Playbooks & Event Quality\n"
        md += "| Event Family (Playbook) | Alerts Triggered |\n"
        md += "|---|---|\n"
        for ev in events:
            md += f"| {ev['event_family']} | {ev['alert_count']} |\n"
        if not events:
            md += "| None | 0 |\n"
        md += "\n"
        
        md += "## 4. AI Provider Health\n"
        md += "| Provider | Requests | Success Rate | 429 Errors | Peak Latency |\n"
        md += "|---|---|---|---|---|\n"
        for ai in ai_usage:
            reqs = ai["reqs"]
            succ = ai["successes"]
            rate = (succ / reqs * 100) if reqs > 0 else 0
            md += f"| {ai['provider']} | {reqs:,} | {rate:.1f}% | {ai['rate_limits']} | {ai['peak_latency']}s |\n"
        if not ai_usage:
            md += "| None | 0 | 0% | 0 | 0s |\n"
        md += "\n"
        
        md += "## 5. Drift & Recommendations\n"
        if worst_sources:
            md += f"- **Source Warning:** The following sources produced high volume (>50) but zero alerts. Consider disabling them to save runtime: {', '.join(worst_sources)}.\n"
        if avg_runtime > 120:
            md += "- **Runtime Warning:** Average runtime exceeds 120 seconds. Check scraper health or increase polling intervals.\n"
        if total_ai > 0 and (total_alerts / total_ai) < 0.05:
            md += "- **Rules Warning:** More than 95% of articles reaching AI are being rejected. Tighten Rules Engine threshold to reduce API costs.\n"
        
        if not worst_sources and avg_runtime <= 120 and (total_ai == 0 or (total_alerts / total_ai) >= 0.05):
            md += "- **Status:** Pipeline operating within nominal institutional parameters. No critical drift detected.\n"

        # Save Report
        out_dir = Path(output_dir)
        out_dir.mkdir(exist_ok=True)
        report_path = out_dir / "OPERATIONS_REPORT.md"
        
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(md)
            
        print(f"[REPORTING] Weekly report saved to {report_path}")
        
    except Exception as e:
        print(f"[ERROR] Failed to generate weekly report: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    generate_weekly_report()