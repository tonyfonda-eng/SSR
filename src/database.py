"""
Special Situations Radar (SSR) 2.0 — Immutable Evidence Engine
Domain-Driven Storage Layer & Telemetry Engine
"""

import sqlite3
import os
import logging
import datetime
import json
import hashlib

logger = logging.getLogger(__name__)

# Strict physical isolation of storage domains
RESEARCH_DB_PATH = "ssr_observability.db"
DEVOPS_DB_PATH = "ssr_devops.db"
AUDIT_DB_PATH = "ssr_audit.db"

# Alias for legacy modules expecting DB_PATH
DB_PATH = RESEARCH_DB_PATH


def init_db():
    """
    Initializes the fully normalized relational schema for the Research Decision Ledger
    and the DevOps Workflow log using strict timezone-aware UTC paradigms.
    """
    os.makedirs(os.path.dirname(os.path.abspath(RESEARCH_DB_PATH)), exist_ok=True)
    r_conn = sqlite3.connect(RESEARCH_DB_PATH)
    r_conn.execute("PRAGMA foreign_keys = ON;")
    
    r_conn.execute("""
        CREATE TABLE IF NOT EXISTS config_snapshots (
            hash TEXT PRIMARY KEY,
            captured_at TEXT NOT NULL,
            run_id TEXT NOT NULL,
            config_json TEXT NOT NULL
        );
    """)

    r_conn.execute("""
        CREATE TABLE IF NOT EXISTS event_registry (
            event_id TEXT PRIMARY KEY,
            article_hash TEXT NOT NULL UNIQUE,
            raw_payload_blob BLOB NOT NULL,
            payload_mime_type TEXT NOT NULL,
            ingest_timestamp TEXT NOT NULL
        );
    """)

    r_conn.execute("""
        CREATE TABLE IF NOT EXISTS evaluation_ledger (
            decision_id TEXT PRIMARY KEY,
            event_id TEXT NOT NULL,
            manifest_hash TEXT NOT NULL,
            runtime_timestamp TEXT NOT NULL,
            detection_outcome TEXT NOT NULL,
            terminal_stage TEXT NOT NULL,
            evidence_completeness_score REAL NOT NULL,
            parent_decision_id TEXT,
            market_data_snapshot TEXT,
            ontology_metadata TEXT,
            execution_timings TEXT,
            FOREIGN KEY (event_id) REFERENCES event_registry(event_id)
        );
    """)

    r_conn.execute("""
        CREATE TABLE IF NOT EXISTS factual_metadata (
            decision_id TEXT PRIMARY KEY,
            headline TEXT,
            source_url TEXT,
            published_timestamp TEXT,
            FOREIGN KEY (decision_id) REFERENCES evaluation_ledger(decision_id)
        );
    """)

    try:
        r_conn.execute("ALTER TABLE evaluation_ledger ADD COLUMN market_data_snapshot TEXT;")
    except sqlite3.OperationalError:
        pass 
        
    try:
        r_conn.execute("ALTER TABLE evaluation_ledger ADD COLUMN ontology_metadata TEXT;")
        r_conn.execute("ALTER TABLE evaluation_ledger ADD COLUMN execution_timings TEXT;")
    except sqlite3.OperationalError:
        pass

    r_conn.execute("""
        CREATE TABLE IF NOT EXISTS atomic_evidence (
            evidence_id TEXT PRIMARY KEY,
            decision_id TEXT NOT NULL,
            stage TEXT NOT NULL,
            evidence_direction TEXT NOT NULL,
            source_component TEXT NOT NULL,
            assertion_key TEXT NOT NULL,
            confidence_weight REAL NOT NULL,
            source_transformation_id TEXT,
            FOREIGN KEY (decision_id) REFERENCES evaluation_ledger(decision_id)
        );
    """)

    # --- FIXED: Brought properly inside init_db() scope ---
    r_conn.execute("""
        CREATE TABLE IF NOT EXISTS article_screening_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            headline TEXT,
            url TEXT,
            source TEXT,
            outcome TEXT NOT NULL,
            final_stage TEXT NOT NULL,
            drop_reason TEXT,
            ticker TEXT,
            company_name TEXT,
            event_family TEXT
        );
    """)
    
    try:
        r_conn.execute("ALTER TABLE article_screening_log ADD COLUMN ingestion_mode TEXT;")
    except sqlite3.OperationalError:
        pass
        
    try:
        r_conn.execute("ALTER TABLE article_screening_log ADD COLUMN company_name TEXT;")
    except sqlite3.OperationalError:
        pass

    r_conn.execute("CREATE INDEX IF NOT EXISTS idx_screening_timestamp ON article_screening_log(timestamp DESC);")
    
    try:
        r_conn.execute("ALTER TABLE event_ledger ADD COLUMN entity_confidence INTEGER;")
        r_conn.execute("ALTER TABLE event_ledger ADD COLUMN event_confidence INTEGER;")
        r_conn.execute("ALTER TABLE event_ledger ADD COLUMN trade_confidence INTEGER;")
        r_conn.execute("ALTER TABLE event_ledger ADD COLUMN financial_quality INTEGER;")
        r_conn.execute("ALTER TABLE event_ledger ADD COLUMN lifecycle TEXT;")
        r_conn.execute("ALTER TABLE event_ledger ADD COLUMN hypotheses TEXT;")
        r_conn.execute("ALTER TABLE event_ledger ADD COLUMN validated_trades TEXT;")
    except sqlite3.OperationalError:
        pass
    
    # --- V4 Event Ledger ---
    r_conn.execute("""
        CREATE TABLE IF NOT EXISTS event_ledger (
            event_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            status TEXT NOT NULL,
            event_type TEXT NOT NULL,
            opportunity_score TEXT,
            entity_confidence INTEGER,
            event_confidence INTEGER,
            trade_confidence INTEGER,
            financial_quality INTEGER,
            confidence_history TEXT,
            hypotheses TEXT,
            validated_trades TEXT,
            evidence TEXT,
            entities TEXT,
            routing_destination TEXT,
            lifecycle TEXT
        );
    """)
    
    r_conn.commit()
    r_conn.close()

    os.makedirs(os.path.dirname(os.path.abspath(DEVOPS_DB_PATH)), exist_ok=True)
    d_conn = sqlite3.connect(DEVOPS_DB_PATH)
    d_conn.execute("""
        CREATE TABLE IF NOT EXISTS workflow_health (
            timestamp TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            total_scanned INTEGER NOT NULL,
            articles INTEGER NOT NULL,
            errors INTEGER NOT NULL,
            drift_score REAL NOT NULL,
            runtime REAL NOT NULL
        );
    """)
    
    try:
        d_conn.execute("ALTER TABLE workflow_health ADD COLUMN funnel_telemetry TEXT;")
    except sqlite3.OperationalError:
        pass
        
    d_conn.commit()
    d_conn.close()

    # --- V4 Audit Database ---
    os.makedirs(os.path.dirname(os.path.abspath(AUDIT_DB_PATH)), exist_ok=True)
    a_conn = sqlite3.connect(AUDIT_DB_PATH)
    a_conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_source_metrics (
            run_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            source TEXT NOT NULL,
            channel TEXT NOT NULL,
            raw_found INTEGER NOT NULL,
            unique_found INTEGER NOT NULL,
            pages_visited INTEGER,
            page_limit INTEGER,
            checkpoint_found BOOLEAN,
            emergency_stop BOOLEAN,
            reason TEXT
        );
    """)
    a_conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_ai_metrics (
            run_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            provider TEXT NOT NULL,
            prompt_type TEXT NOT NULL,
            input_tokens INTEGER,
            output_tokens INTEGER,
            latency_ms INTEGER,
            cost REAL,
            success BOOLEAN
        );
    """)
    a_conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            run_id TEXT NOT NULL,
            source_or_provider TEXT NOT NULL,
            event_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            details TEXT
        );
    """)
    a_conn.commit()
    a_conn.close()

# MODULE-LEVEL EXPORTS REQUIRED BY MONITOR.PY
def initialise_database():
    init_db()

def get_latest_config_snapshot() -> dict:
    try:
        conn = sqlite3.connect(RESEARCH_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT hash, captured_at, run_id, config_json FROM config_snapshots ORDER BY captured_at DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        if row:
            return {"hash": row[0], "captured_at": row[1], "run_id": row[2], "config_json": row[3]}
        return None
    except Exception:
        return None

def save_config_snapshot(config_hash: str, run_id: str, config_json: str):
    try:
        gmt_now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT")
        conn = sqlite3.connect(RESEARCH_DB_PATH)
        conn.execute("INSERT OR IGNORE INTO config_snapshots (hash, captured_at, run_id, config_json) VALUES (?, ?, ?, ?);", 
                     (config_hash, gmt_now, run_id, config_json))
        conn.commit()
        conn.close()
    except Exception:
        pass

def get_or_create_event(article_hash: str, raw_payload: bytes, mime_type: str = "text/html") -> tuple:
    conn = sqlite3.connect(RESEARCH_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT event_id FROM event_registry WHERE article_hash = ? LIMIT 1;", (article_hash,))
    row = cursor.fetchone()
    if row:
        event_id = row[0]
        conn.close()
        return event_id, False
        
    gmt_now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT")
    event_id = f"EVT-{hashlib.md5(article_hash.encode('utf-8')).hexdigest()[:12].upper()}"
    
    try:
        cursor.execute("INSERT INTO event_registry (event_id, article_hash, raw_payload_blob, payload_mime_type, ingest_timestamp) VALUES (?, ?, ?, ?, ?);",
                       (event_id, article_hash, sqlite3.Binary(raw_payload), mime_type, gmt_now))
        conn.commit()
        conn.close()
        return event_id, True
    except Exception:
        conn.close()
        return f"ERR-{event_id}", True

def log_article_screening(entry: dict) -> None:
    try:
        gmt_now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT")
        conn = sqlite3.connect(RESEARCH_DB_PATH)
        conn.execute("""
            INSERT INTO article_screening_log
            (run_id, timestamp, headline, url, source, outcome, final_stage, drop_reason, ticker, company_name, event_family, ingestion_mode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            entry.get("run_id", "UNKNOWN"),
            gmt_now,
            (entry.get("headline") or "")[:500],
            entry.get("url", ""),
            entry.get("source", ""),
            entry.get("outcome", "UNKNOWN"),
            entry.get("final_stage", "UNKNOWN"),
            entry.get("drop_reason"),
            entry.get("ticker"),
            entry.get("company_name"),
            entry.get("event_family"),
            entry.get("ingestion_mode", "UNKNOWN")
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"[DB FAULT] Failed to write article_screening_log: {e}")
        
def commit_decision_capsule(capsule_data: dict, manifest_json: dict = None):
    try:
        conn = sqlite3.connect(RESEARCH_DB_PATH)
        cursor = conn.cursor()
        dec_id = capsule_data["decision_id"]
        
        cursor.execute("""
            INSERT OR REPLACE INTO evaluation_ledger 
            (decision_id, event_id, manifest_hash, runtime_timestamp, detection_outcome, terminal_stage, evidence_completeness_score, market_data_snapshot, ontology_metadata, execution_timings)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            dec_id,
            capsule_data["event_id"],
            capsule_data["manifest_hash"],
            capsule_data.get("runtime_timestamp", datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT")),
            capsule_data["detection_outcome"],
            capsule_data["terminal_stage"],
            capsule_data.get("evidence_completeness_score", 1.0),
            capsule_data.get("market_data_snapshot"),
            json.dumps(capsule_data.get("ontology_metadata", {})),
            json.dumps(capsule_data.get("execution_timings", {}))
        ))
        
        cursor.execute("""
            INSERT OR REPLACE INTO factual_metadata (decision_id, headline, source_url, published_timestamp)
            VALUES (?, ?, ?, ?);
        """, (
            dec_id,
            capsule_data.get("headline", "Corporate Announcement"),
            capsule_data.get("url", "http://local.endpoint"),
            capsule_data.get("runtime_timestamp")
        ))
        
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"[DB FAULT] Capsule commit failed: {e}")

def log_event(event_data: dict):
    import json
    conn = sqlite3.connect(RESEARCH_DB_PATH)
    try:
        opportunity_score_dict = event_data.get("opportunity_score", {})
        conn.execute("""
            INSERT OR REPLACE INTO event_ledger (
                event_id, created_at, updated_at, status, event_type,
                opportunity_score, entity_confidence, event_confidence, trade_confidence, financial_quality,
                confidence_history, trade_graph, evidence, entities, routing_destination, lifecycle
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event_data["event_id"],
            event_data["created_at"],
            event_data["updated_at"],
            event_data["status"],
            event_data["event_type"],
            json.dumps(opportunity_score_dict),
            opportunity_score_dict.get("entity_confidence"),
            opportunity_score_dict.get("event_confidence"),
            opportunity_score_dict.get("trade_confidence"),
            opportunity_score_dict.get("financial_quality"),
            json.dumps(event_data.get("confidence_history", [])),
            json.dumps(event_data.get("trade_graph", [])),
            json.dumps(event_data.get("evidence", [])),
            json.dumps(event_data.get("entities", [])),
            event_data.get("routing_destination", "DROPPED"),
            json.dumps(event_data.get("lifecycle", []))
        ))
        conn.commit()
    finally:
        conn.close()

def save_workflow_health(health_data=None):
    try:
        gmt_now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT")
        conn = sqlite3.connect(DEVOPS_DB_PATH)
        
        funnel_json = json.dumps(health_data.get('funnel', {})) if health_data else "{}"
        
        conn.execute("""
            INSERT OR REPLACE INTO workflow_health (timestamp, run_id, total_scanned, articles, errors, drift_score, runtime, funnel_telemetry)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            gmt_now,
            health_data.get('run_id', 'UNKNOWN') if health_data else 'UNKNOWN',
            health_data.get('total_scanned', 0) if health_data else 0,
            health_data.get('articles', 0) if health_data else 0,
            health_data.get('errors', 0) if health_data else 0,
            health_data.get('drift_score', 0.0) if health_data else 0.0,
            health_data.get('runtime', 0.0) if health_data else 0.0,
            funnel_json
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"[DB FAULT] Failed to save workflow health: {e}")

def save_exception_log(*args, **kwargs): pass
def save_source_stats(*args, **kwargs): pass

def log_audit_source_metrics(run_id: str, ledger: list):
    try:
        gmt_now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT")
        conn = sqlite3.connect(AUDIT_DB_PATH)
        for entry in ledger:
            meta = entry.get("metadata", {})
            conn.execute("""
                INSERT INTO daily_source_metrics 
                (run_id, timestamp, source, channel, raw_found, unique_found, pages_visited, page_limit, checkpoint_found, emergency_stop, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                run_id, gmt_now, entry.get("source"), entry.get("channel"),
                entry.get("raw_found", 0), entry.get("unique_found", 0),
                meta.get("pages_visited", 0), meta.get("page_limit", 0),
                meta.get("checkpoint_found", False), meta.get("emergency_stop", False), meta.get("reason", "")
            ))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"[DB FAULT] Failed to write daily_source_metrics: {e}")

def log_audit_ai_metrics(run_id: str, telemetry: list):
    try:
        gmt_now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT")
        conn = sqlite3.connect(AUDIT_DB_PATH)
        for t in telemetry:
            conn.execute("""
                INSERT INTO daily_ai_metrics 
                (run_id, timestamp, provider, prompt_type, input_tokens, output_tokens, latency_ms, cost, success)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                run_id, gmt_now, t.get("provider"), t.get("prompt_type"),
                t.get("input_tokens", 0), t.get("output_tokens", 0),
                t.get("latency_ms", 0), t.get("cost", 0.0), t.get("success", False)
            ))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"[DB FAULT] Failed to write daily_ai_metrics: {e}")

def log_audit_event(run_id: str, source_or_provider: str, event_type: str, severity: str, details: str):
    """Writes a black-box event log directly to the audit database."""
    try:
        gmt_now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT")
        conn = sqlite3.connect(AUDIT_DB_PATH)
        conn.execute("""
            INSERT INTO audit_events 
            (timestamp, run_id, source_or_provider, event_type, severity, details)
            VALUES (?, ?, ?, ?, ?, ?);
        """, (
            gmt_now, run_id, source_or_provider, event_type, severity, details
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"[DB FAULT] Failed to write audit event: {e}")