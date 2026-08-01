import sqlite3
from pathlib import Path
import datetime
import contextlib

DB_PATH = Path(__file__).resolve().parent.parent / "ssr_cache.sqlite"

@contextlib.contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def initialise_database():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                article_key TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                article_id TEXT NOT NULL,
                title TEXT,
                url TEXT,
                published TEXT,
                body TEXT,
                processed_at TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS companies (
                ticker TEXT PRIMARY KEY,
                first_seen TEXT,
                alert_count INTEGER DEFAULT 0
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                event_family TEXT,
                target_ticker TEXT,
                status TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS research_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT,
                article_id TEXT,
                rules_score INTEGER,
                ai_summary TEXT,
                processed_at TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                reminder_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT,
                ticker TEXT,
                reminder_date TEXT,
                message TEXT,
                sent INTEGER DEFAULT 0
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS article_lifecycle_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id TEXT,
                timestamp TEXT,
                source TEXT,
                title TEXT,
                url TEXT,
                country TEXT,
                language TEXT,
                document_type TEXT,
                issuer TEXT,
                event_family TEXT,
                pipeline_stage TEXT,
                outcome TEXT,
                reason TEXT,
                ai_invoked INTEGER,
                processing_time_ms INTEGER,
                slowest_stage TEXT
            )
        """)

        # Operational Datastore Tables
        conn.execute("""
            CREATE TABLE IF NOT EXISTS run_metrics_log (
                run_id TEXT PRIMARY KEY,
                timestamp TEXT,
                downloaded INTEGER,
                unique_articles INTEGER,
                duplicates INTEGER,
                passed_regex INTEGER,
                failed_regex INTEGER,
                global_exclusions INTEGER,
                ontology_matches INTEGER,
                rules_passes INTEGER,
                rules_failures INTEGER,
                ai_calls INTEGER,
                ai_successes INTEGER,
                ai_failures INTEGER,
                playbooks_executed INTEGER,
                emails_sent INTEGER,
                rules_score_sum REAL,
                ai_confidence_sum REAL,
                articles_processed_count INTEGER,
                total_runtime_s REAL,
                rejected_before_regex INTEGER,
                rejected_by_regex INTEGER,
                rejected_by_exclusions INTEGER,
                rejected_by_ontology INTEGER,
                rejected_by_rules INTEGER,
                reached_ai INTEGER
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS ai_usage_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                timestamp TEXT,
                provider TEXT,
                key_id TEXT,
                requests INTEGER,
                success INTEGER,
                failures INTEGER,
                errors_429 INTEGER,
                errors_503 INTEGER,
                timeouts INTEGER,
                retries INTEGER,
                fallbacks INTEGER,
                response_time_sum REAL,
                max_latency REAL,
                last_success_ts TEXT,
                last_failure_ts TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS source_stats_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                timestamp TEXT,
                source TEXT,
                downloaded INTEGER,
                survived_regex INTEGER,
                survived_ontology INTEGER,
                survived_rules INTEGER,
                reached_ai INTEGER,
                alerts INTEGER,
                processing_time_sum REAL,
                processed_count INTEGER
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS workflow_health (
                run_id TEXT PRIMARY KEY,
                date TEXT,
                timestamp TEXT,
                success INTEGER,
                failed INTEGER,
                runtime REAL,
                articles INTEGER,
                emails INTEGER,
                git_commit TEXT,
                branch TEXT,
                python_version TEXT,
                exception TEXT,
                workflow_version TEXT,
                run_number TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS exceptions_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                timestamp TEXT,
                exc_type TEXT,
                stack_trace TEXT,
                module TEXT,
                func_name TEXT,
                article_url TEXT,
                severity TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS sheets_sync_log (
                date TEXT PRIMARY KEY,
                synced_at TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS source_hourly_heatmap (
                source TEXT,
                hour_utc INTEGER,
                avg_volume REAL DEFAULT 0.0,
                PRIMARY KEY (source, hour_utc)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS dashboard_state (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        try:
            conn.execute("ALTER TABLE articles ADD COLUMN body TEXT")
        except sqlite3.OperationalError:
            pass
            
        try:
            conn.execute("ALTER TABLE reminders ADD COLUMN ticker TEXT")
        except sqlite3.OperationalError:
            pass
            
        try:
            # Upgrade run metrics for funnel explicitly
            conn.execute("ALTER TABLE run_metrics_log ADD COLUMN rejected_before_regex INTEGER DEFAULT 0")
            conn.execute("ALTER TABLE run_metrics_log ADD COLUMN rejected_by_regex INTEGER DEFAULT 0")
            conn.execute("ALTER TABLE run_metrics_log ADD COLUMN rejected_by_exclusions INTEGER DEFAULT 0")
            conn.execute("ALTER TABLE run_metrics_log ADD COLUMN rejected_by_ontology INTEGER DEFAULT 0")
            conn.execute("ALTER TABLE run_metrics_log ADD COLUMN rejected_by_rules INTEGER DEFAULT 0")
            conn.execute("ALTER TABLE run_metrics_log ADD COLUMN reached_ai INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass

    print("[DATABASE] Ready")

def article_exists(article_key):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM articles WHERE article_key = ?", (article_key,))
        return cursor.fetchone() is not None

def save_article(source, article_id, title, url, published, body):
    with get_connection() as conn:
        cursor = conn.cursor()
        article_key = f"{source}:{article_id}"
        processed_at = datetime.datetime.now().isoformat()
        cursor.execute("""
            INSERT OR REPLACE INTO articles (article_key, source, article_id, title, url, published, body, processed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (article_key, source, article_id, title, url, published, body, processed_at))

def article_count():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM articles")
        return cursor.fetchone()[0]

def track_company(ticker):
    with get_connection() as conn:
        cursor = conn.cursor()
        now = datetime.datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO companies (ticker, first_seen, alert_count)
            VALUES (?, ?, 1)
            ON CONFLICT(ticker) DO UPDATE SET alert_count = alert_count + 1
        """, (ticker, now))

def create_event_if_new(event_family, ticker):
    now = datetime.datetime.now()
    event_id = f"{ticker}_{now.year}_{now.month:02d}_{now.day:02d}"
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM events WHERE event_id = ?", (event_id,))
        if cursor.fetchone() is not None:
            return event_id, False
            
        cursor.execute("""
            INSERT INTO events (event_id, event_family, target_ticker, status, created_at, updated_at)
            VALUES (?, ?, ?, 'Announced', ?, ?)
        """, (event_id, event_family, ticker, now.isoformat(), now.isoformat()))
        return event_id, True

def log_research(event_id, article_id, rules_score, ai_summary):
    with get_connection() as conn:
        cursor = conn.cursor()
        now = datetime.datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO research_logs (event_id, article_id, rules_score, ai_summary, processed_at)
            VALUES (?, ?, ?, ?, ?)
        """, (event_id, article_id, rules_score, ai_summary, now))

def save_reminder(event_id, ticker, reminder_date, message):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO reminders (event_id, ticker, reminder_date, message)
            VALUES (?, ?, ?, ?)
        """, (event_id, ticker, reminder_date, message))

def get_pending_reminders():
    with get_connection() as conn:
        cursor = conn.cursor()
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        cursor.execute("""
            SELECT reminder_id, event_id, ticker, reminder_date, message 
            FROM reminders 
            WHERE reminder_date <= ? AND sent = 0
        """, (today,))
        reminders = cursor.fetchall()
        return [{'id': r[0], 'event_id': r[1], 'ticker': r[2], 'date': r[3], 'message': r[4]} for r in reminders]

def mark_reminder_sent(reminder_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE reminders SET sent = 1 WHERE reminder_id = ?", (reminder_id,))

def get_dashboard_state(key, default=None):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM dashboard_state WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row[0] if row else default

def set_dashboard_state(key, value):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO dashboard_state (key, value) VALUES (?, ?)", (key, str(value)))

def save_lifecycle_logs(logs):
    if not logs: return
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.executemany("""
            INSERT INTO article_lifecycle_log (
                article_id, timestamp, source, title, url, country, language, 
                document_type, issuer, event_family, pipeline_stage, outcome, reason, ai_invoked, processing_time_ms, slowest_stage
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, logs)

def perform_housekeeping():
    with get_connection() as conn:
        cursor = conn.cursor()
        now = datetime.datetime.utcnow()
        
        # 14 days for lifecycle logs
        cutoff_14 = (now - datetime.timedelta(days=14)).isoformat()
        cursor.execute("DELETE FROM article_lifecycle_log WHERE timestamp < ?", (cutoff_14,))
        
        # 90 days for exceptions
        cutoff_90 = (now - datetime.timedelta(days=90)).isoformat()
        cursor.execute("DELETE FROM exceptions_log WHERE timestamp < ?", (cutoff_90,))
        
        # 365 days for run metrics
        cutoff_365 = (now - datetime.timedelta(days=365)).isoformat()
        cursor.execute("DELETE FROM run_metrics_log WHERE timestamp < ?", (cutoff_365,))
        # also clean source stats
        cursor.execute("DELETE FROM source_stats_log WHERE timestamp < ?", (cutoff_365,))
        
    set_dashboard_state('last_cleanup', now.isoformat())

def get_recent_lifecycle_logs():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT timestamp, source, title, url, country, language, document_type, issuer, event_family, pipeline_stage, outcome, reason, ai_invoked, processing_time_ms, slowest_stage
            FROM article_lifecycle_log
            ORDER BY timestamp DESC
        """)
        rows = cursor.fetchall()
        return [{
            "timestamp": r[0], "source": r[1], "title": r[2], "url": r[3], "country": r[4], 
            "language": r[5], "document_type": r[6], "issuer": r[7], "event_family": r[8], 
            "pipeline_stage": r[9], "outcome": r[10], "reason": r[11], "ai_invoked": r[12], "processing_time_ms": r[13], "slowest_stage": r[14]
        } for r in rows]

def save_run_metrics(run_metrics):
    with get_connection() as conn:
        conn.cursor().execute("""
            INSERT INTO run_metrics_log (
                run_id, timestamp, downloaded, unique_articles, duplicates, passed_regex, failed_regex, 
                global_exclusions, ontology_matches, rules_passes, rules_failures, ai_calls, ai_successes, 
                ai_failures, playbooks_executed, emails_sent, rules_score_sum, ai_confidence_sum, 
                articles_processed_count, total_runtime_s, rejected_before_regex, rejected_by_regex,
                rejected_by_exclusions, rejected_by_ontology, rejected_by_rules, reached_ai
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_metrics["run_id"], run_metrics["timestamp"], run_metrics["downloaded"], run_metrics["unique"],
            run_metrics["duplicates"], run_metrics["passed_regex"], run_metrics["failed_regex"], 
            run_metrics["global_exclusions"], run_metrics["ontology_matches"], run_metrics["rules_passes"], 
            run_metrics["rules_failures"], run_metrics["ai_calls"], run_metrics["ai_successes"], 
            run_metrics["ai_failures"], run_metrics["playbooks_executed"], run_metrics["emails_sent"], 
            run_metrics["rules_score_sum"], run_metrics["ai_confidence_sum"], run_metrics["articles_processed_count"], 
            run_metrics["total_runtime_s"], run_metrics.get("rejected_before_regex", 0), run_metrics.get("rejected_by_regex", 0),
            run_metrics.get("rejected_by_exclusions", 0), run_metrics.get("rejected_by_ontology", 0), 
            run_metrics.get("rejected_by_rules", 0), run_metrics.get("reached_ai", 0)
        ))

def save_ai_usage(ai_usage_rows):
    if not ai_usage_rows: return
    with get_connection() as conn:
        conn.cursor().executemany("""
            INSERT INTO ai_usage_log (
                run_id, timestamp, provider, key_id, requests, success, failures, errors_429, errors_503,
                timeouts, retries, fallbacks, response_time_sum, max_latency, last_success_ts, last_failure_ts
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ai_usage_rows)

def save_source_stats(source_stats_rows):
    if not source_stats_rows: return
    with get_connection() as conn:
        conn.cursor().executemany("""
            INSERT INTO source_stats_log (
                run_id, timestamp, source, downloaded, survived_regex, survived_ontology, survived_rules,
                reached_ai, alerts, processing_time_sum, processed_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, source_stats_rows)

def save_workflow_health(wh):
    with get_connection() as conn:
        conn.cursor().execute("""
            INSERT INTO workflow_health (
                run_id, date, timestamp, success, failed, runtime, articles, emails, git_commit, branch, python_version, exception, workflow_version, run_number
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            wh["run_id"], wh["date"], wh["timestamp"], wh["success"], wh["failed"], wh["runtime"],
            wh["articles"], wh["emails"], wh["git_commit"], wh["branch"], wh["python_version"], wh["exception"], wh.get("workflow_version", "1.0"), wh.get("run_number", "1")
        ))

def save_exception_log(run_id, timestamp, exc_type, stack_trace, module, func_name, article_url, severity):
    with get_connection() as conn:
        conn.cursor().execute("""
            INSERT INTO exceptions_log (
                run_id, timestamp, exc_type, stack_trace, module, func_name, article_url, severity
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (run_id, timestamp, exc_type, stack_trace, module, func_name, article_url, severity))

def is_yesterday_synced():
    with get_connection() as conn:
        cursor = conn.cursor()
        yesterday = (datetime.datetime.utcnow() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        cursor.execute("SELECT 1 FROM sheets_sync_log WHERE date = ?", (yesterday,))
        return cursor.fetchone() is not None

def mark_yesterday_synced():
    with get_connection() as conn:
        cursor = conn.cursor()
        yesterday = (datetime.datetime.utcnow() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        now = datetime.datetime.utcnow().isoformat()
        cursor.execute("INSERT OR REPLACE INTO sheets_sync_log (date, synced_at) VALUES (?, ?)", (yesterday, now))
    set_dashboard_state('last_daily_sync', now)

def get_yesterdays_metrics():
    """Aggregates all metrics for yesterday from SQLite to sync to Google Sheets."""
    with get_connection() as conn:
        cursor = conn.cursor()
        yesterday = (datetime.datetime.utcnow() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        
        cursor.execute("""
            SELECT 
                SUM(downloaded), SUM(unique_articles), SUM(duplicates), SUM(passed_regex), SUM(failed_regex),
                SUM(global_exclusions), SUM(ontology_matches), SUM(rules_passes), SUM(rules_failures),
                SUM(ai_calls), SUM(ai_successes), SUM(ai_failures), SUM(playbooks_executed), SUM(emails_sent),
                SUM(rules_score_sum), SUM(ai_confidence_sum), SUM(articles_processed_count),
                MAX(total_runtime_s), SUM(total_runtime_s)
            FROM run_metrics_log
            WHERE date(timestamp) = ?
        """, (yesterday,))
        daily = cursor.fetchone()
        
        cursor.execute("""
            SELECT 
                provider, key_id, SUM(requests), SUM(success), SUM(failures), SUM(errors_429), SUM(errors_503),
                SUM(timeouts), SUM(retries), SUM(fallbacks), SUM(response_time_sum), MAX(max_latency),
                MAX(last_success_ts), MAX(last_failure_ts)
            FROM ai_usage_log
            WHERE date(timestamp) = ?
            GROUP BY provider, key_id
        """, (yesterday,))
        ai = cursor.fetchall()
        
        cursor.execute("""
            SELECT 
                source, SUM(downloaded), SUM(survived_regex), SUM(survived_ontology), SUM(survived_rules),
                SUM(reached_ai), SUM(alerts), SUM(processing_time_sum), SUM(processed_count)
            FROM source_stats_log
            WHERE date(timestamp) = ?
            GROUP BY source
        """, (yesterday,))
        sources = cursor.fetchall()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as runs, SUM(success), SUM(failed), SUM(runtime), SUM(articles), SUM(emails)
            FROM workflow_health
            WHERE date(timestamp) = ?
        """, (yesterday,))
        workflow = cursor.fetchone()
        
        return {
            "date": yesterday,
            "daily_stats": daily,
            "ai_usage": ai,
            "source_stats": sources,
            "workflow_health": workflow
        }

def get_30_day_average():
    """Calculates the 30-day trailing averages for key metrics."""
    with get_connection() as conn:
        cursor = conn.cursor()
        end_date = (datetime.datetime.utcnow() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        start_date = (datetime.datetime.utcnow() - datetime.timedelta(days=31)).strftime("%Y-%m-%d")
        
        cursor.execute("""
            SELECT 
                SUM(downloaded)/30.0 as avg_downloaded,
                SUM(passed_regex)/30.0 as avg_passed_regex,
                SUM(rules_passes)/30.0 as avg_rules_passes,
                SUM(ai_calls)/30.0 as avg_ai_calls,
                SUM(emails_sent)/30.0 as avg_emails_sent
            FROM run_metrics_log
            WHERE date(timestamp) >= ? AND date(timestamp) <= ?
        """, (start_date, end_date))
        
        row = cursor.fetchone()
        if not row or row[0] is None:
            return None
            
        return {
            "downloaded": row[0],
            "passed_regex": row[1],
            "rules_passes": row[2],
            "ai_calls": row[3],
            "emails_sent": row[4]
        }

def get_30_day_source_averages():
    """Calculates the 30-day trailing averages per source."""
    with get_connection() as conn:
        cursor = conn.cursor()
        end_date = (datetime.datetime.utcnow() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        start_date = (datetime.datetime.utcnow() - datetime.timedelta(days=31)).strftime("%Y-%m-%d")
        
        cursor.execute("""
            SELECT 
                source,
                SUM(downloaded)/30.0 as avg_downloaded,
                SUM(alerts)/30.0 as avg_alerts
            FROM source_stats_log
            WHERE date(timestamp) >= ? AND date(timestamp) <= ?
            GROUP BY source
        """, (start_date, end_date))
        
        rows = cursor.fetchall()
        averages = {}
        for row in rows:
            averages[row[0]] = {
                "avg_downloaded": row[1] or 0.0,
                "avg_alerts": row[2] or 0.0
            }
        return averages

def update_hourly_volume(source_counts, hour_utc, alpha=0.1):
    """
    Updates the historical exponential moving average of article volume per source per hour.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        for source, count in source_counts.items():
            cursor.execute("SELECT avg_volume FROM source_hourly_heatmap WHERE source = ? AND hour_utc = ?", (source, hour_utc))
            row = cursor.fetchone()
            
            if row:
                old_avg = row[0]
                new_avg = (old_avg * (1.0 - alpha)) + (count * alpha)
            else:
                new_avg = float(count)
                
            cursor.execute("""
                INSERT OR REPLACE INTO source_hourly_heatmap (source, hour_utc, avg_volume)
                VALUES (?, ?, ?)
            """, (source, hour_utc, new_avg))

def get_hourly_heatmap(hour_utc=None):
    """
    Returns a dictionary of {source: avg_volume} for the specified UTC hour.
    """
    if hour_utc is None:
        hour_utc = datetime.datetime.utcnow().hour
        
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT source, avg_volume FROM source_hourly_heatmap WHERE hour_utc = ?", (hour_utc,))
        return {row[0]: row[1] for row in cursor.fetchall()}

def export_archive_json(filepath="docs/archive_data.json", limit=10000):
    """
    Exports the latest archived articles (excluding body text) to a JSON file 
    for the DataTables web frontend.
    """
    import json
    import os
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT source, title, url, published, processed_at
            FROM articles
            ORDER BY processed_at DESC
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        data = []
        for r in rows:
            data.append({
                "source": r[0] or "",
                "title": r[1] or "",
                "url": r[2] or "",
                "published": r[3] or "",
                "processed_at": r[4] or ""
            })
            
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
        
    print(f"[DATABASE] Exported {len(data)} articles to {filepath} for Web Archive.")