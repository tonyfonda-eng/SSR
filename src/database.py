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

def _get_connection(db_path: str):
    conn = sqlite3.connect(db_path, timeout=30.0)
    # Ensure WAL mode is active for concurrency
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn


def init_db():
    """
    Initializes the fully normalized relational schema for the Research Decision Ledger
    and the DevOps Workflow log using strict timezone-aware UTC paradigms.
    """
    os.makedirs(os.path.dirname(os.path.abspath(RESEARCH_DB_PATH)), exist_ok=True)
    r_conn = _get_connection(RESEARCH_DB_PATH)
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

    try:
        r_conn.execute("ALTER TABLE article_screening_log ADD COLUMN body_sha256 TEXT;")
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
        r_conn.execute("ALTER TABLE event_ledger ADD COLUMN human_review_flag INTEGER DEFAULT 0;")
        r_conn.execute("ALTER TABLE event_ledger ADD COLUMN merge_decision TEXT;")
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
            lifecycle TEXT,
            human_review_flag INTEGER DEFAULT 0,
            merge_decision TEXT
        );
    """)

    # --- V4 Shadow Ledger ---
    r_conn.execute("""
        CREATE TABLE IF NOT EXISTS v4_event_ledger (
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
            lifecycle TEXT,
            human_review_flag INTEGER DEFAULT 0,
            merge_decision TEXT,
            v2_outcome TEXT,
            event_trace TEXT,
            article_hash TEXT,
            v4_run_id TEXT,
            parent_run_id TEXT,
            v4_outcome TEXT
        );
    """)
    
    try:
        r_conn.execute("ALTER TABLE v4_event_ledger ADD COLUMN v2_outcome TEXT;")
    except sqlite3.OperationalError: pass
    try:
        r_conn.execute("ALTER TABLE v4_event_ledger ADD COLUMN event_trace TEXT;")
    except sqlite3.OperationalError: pass
    try:
        r_conn.execute("ALTER TABLE v4_event_ledger ADD COLUMN article_hash TEXT;")
    except sqlite3.OperationalError: pass
    try:
        r_conn.execute("ALTER TABLE v4_event_ledger ADD COLUMN v4_run_id TEXT;")
    except sqlite3.OperationalError: pass
    try:
        r_conn.execute("ALTER TABLE v4_event_ledger ADD COLUMN parent_run_id TEXT;")
    except sqlite3.OperationalError: pass
    try:
        r_conn.execute("ALTER TABLE v4_event_ledger ADD COLUMN v4_outcome TEXT;")
    except sqlite3.OperationalError: pass
    
    r_conn.commit()
    r_conn.close()

    os.makedirs(os.path.dirname(os.path.abspath(DEVOPS_DB_PATH)), exist_ok=True)
    d_conn = _get_connection(DEVOPS_DB_PATH)
    d_conn.execute("""
        CREATE TABLE IF NOT EXISTS workflow_health (
            timestamp TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            total_scanned INTEGER NOT NULL,
            articles INTEGER NOT NULL,
            errors INTEGER NOT NULL,
            drift_score REAL NOT NULL,
            runtime REAL NOT NULL,
            engine_version TEXT,
            execution_mode TEXT,
            parent_run_id TEXT
        );
    """)
    
    try:
        d_conn.execute("ALTER TABLE workflow_health ADD COLUMN funnel_telemetry TEXT;")
    except sqlite3.OperationalError:
        pass
    try:
        d_conn.execute("ALTER TABLE workflow_health ADD COLUMN engine_version TEXT;")
    except sqlite3.OperationalError:
        pass
    try:
        d_conn.execute("ALTER TABLE workflow_health ADD COLUMN execution_mode TEXT;")
    except sqlite3.OperationalError:
        pass
    try:
        d_conn.execute("ALTER TABLE workflow_health ADD COLUMN parent_run_id TEXT;")
    except sqlite3.OperationalError:
        pass
        
    d_conn.commit()
    d_conn.close()

    # --- V4 Audit Database ---
    os.makedirs(os.path.dirname(os.path.abspath(AUDIT_DB_PATH)), exist_ok=True)
    a_conn = _get_connection(AUDIT_DB_PATH)
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
    try:
        a_conn.execute("ALTER TABLE daily_source_metrics ADD COLUMN valid_url_count INTEGER DEFAULT 0;")
        a_conn.execute("ALTER TABLE daily_source_metrics ADD COLUMN valid_title_count INTEGER DEFAULT 0;")
        a_conn.execute("ALTER TABLE daily_source_metrics ADD COLUMN valid_body_count INTEGER DEFAULT 0;")
        a_conn.execute("ALTER TABLE daily_source_metrics ADD COLUMN entered_dedupe_count INTEGER DEFAULT 0;")
        a_conn.execute("ALTER TABLE daily_source_metrics ADD COLUMN dedupe_passed_count INTEGER DEFAULT 0;")
        a_conn.execute("ALTER TABLE daily_source_metrics ADD COLUMN dedupe_rejected_count INTEGER DEFAULT 0;")
    except sqlite3.OperationalError: pass
    
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
    a_conn.execute("""
        CREATE TABLE IF NOT EXISTS email_dispatch_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL,
            decision_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            recipient TEXT,
            smtp_host TEXT,
            smtp_port INTEGER,
            attempt_number INTEGER,
            outcome_state TEXT NOT NULL,
            exception_class TEXT,
            exception_message TEXT,
            provider_response TEXT
        );
    """)
    a_conn.commit()
    a_conn.close()

# MODULE-LEVEL EXPORTS REQUIRED BY MONITOR.PY
def initialise_database():
    init_db()

def get_latest_config_snapshot() -> dict:
    try:
        conn = _get_connection(RESEARCH_DB_PATH)
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
    conn = _get_connection(RESEARCH_DB_PATH)
    try:
        gmt_now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT")
        conn.execute("INSERT OR IGNORE INTO config_snapshots (hash, captured_at, run_id, config_json) VALUES (?, ?, ?, ?);", 
                     (config_hash, gmt_now, run_id, config_json))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()

def check_event_exists(article_hash: str) -> tuple:
    conn = _get_connection(RESEARCH_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT event_id FROM event_registry WHERE article_hash = ? LIMIT 1;", (article_hash,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row[0], False
        
    event_id = f"EVT-{hashlib.md5(article_hash.encode('utf-8')).hexdigest()[:12].upper()}"
    return event_id, True

def log_article_screening(entry: dict) -> None:
    conn = _get_connection(RESEARCH_DB_PATH)
    try:
        gmt_now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT")
        conn.execute("""
            INSERT INTO article_screening_log
            (run_id, timestamp, headline, url, source, outcome, final_stage, drop_reason, ticker, company_name, event_family, ingestion_mode, body_sha256)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
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
            entry.get("ingestion_mode", "UNKNOWN"),
            entry.get("body_sha256")
        ))
        conn.commit()
    except Exception as e:
        logger.error(f"[DB FAULT] Failed to write article_screening_log: {e}")
    finally:
        conn.close()
        
def commit_decision_capsule(capsule_data: dict, manifest_json: dict = None):
    conn = _get_connection(RESEARCH_DB_PATH)
    try:
        cursor = conn.cursor()
        
        # Atomically register the dedupe identity and the decision ledger
        if "article_hash" in capsule_data and "raw_payload_blob" in capsule_data:
            gmt_now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT")
            cursor.execute("""
                INSERT OR IGNORE INTO event_registry (event_id, article_hash, raw_payload_blob, payload_mime_type, ingest_timestamp)
                VALUES (?, ?, ?, ?, ?);
            """, (
                capsule_data["event_id"],
                capsule_data["article_hash"],
                sqlite3.Binary(capsule_data["raw_payload_blob"]),
                capsule_data.get("payload_mime_type", "text/html"),
                gmt_now
            ))
            
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
    except Exception as e:
        logger.error(f"[DB FAULT] Capsule commit failed: {e}")
        raise
    finally:
        conn.close()

def log_event(event_data: dict):
    import json
    conn = _get_connection(RESEARCH_DB_PATH)
    try:
        opportunity_score_dict = event_data.get("opportunity_score", {})
        conn.execute("""
            INSERT OR REPLACE INTO event_ledger (
                event_id, created_at, updated_at, status, event_type,
                opportunity_score, entity_confidence, event_confidence, trade_confidence, financial_quality,
                confidence_history, hypotheses, validated_trades, evidence, entities, routing_destination, lifecycle, human_review_flag, merge_decision
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            json.dumps(event_data.get("hypotheses", [])),
            json.dumps(event_data.get("validated_trades", [])),
            json.dumps(event_data.get("evidence", [])),
            json.dumps(event_data.get("entities", [])),
            event_data.get("routing_destination", "DROPPED"),
            json.dumps(event_data.get("lifecycle", [])),
            event_data.get("human_review_flag", 0),
            json.dumps(event_data.get("merge_decision", {})) if event_data.get("merge_decision") else None
        ))
        conn.commit()
    finally:
        conn.close()

def log_v4_shadow_event(event_data: dict):
    import json
    conn = _get_connection(RESEARCH_DB_PATH)
    try:
        event_id = event_data["event_id"]
        cursor = conn.cursor()
        
        # Read existing record to handle append-aware fields
        cursor.execute("SELECT confidence_history, evidence, event_trace FROM v4_event_ledger WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()
        
        new_conf = event_data.get("confidence_history", [])
        new_evidence = event_data.get("evidence", [])
        new_trace = event_data.get("event_trace", "")
        
        if row:
            # Safely append arrays
            try:
                old_conf = json.loads(row[0]) if row[0] else []
                for item in new_conf:
                    if item not in old_conf:
                        old_conf.append(item)
                new_conf = old_conf
            except: pass
            
            try:
                old_evidence = json.loads(row[1]) if row[1] else []
                for item in new_evidence:
                    if item not in old_evidence:
                        old_evidence.append(item)
                new_evidence = old_evidence
            except: pass
            
            try:
                old_traces = json.loads(row[2]) if row[2] else []
                if isinstance(old_traces, dict): old_traces = [old_traces]
                if new_trace:
                    new_trace_obj = json.loads(new_trace) if isinstance(new_trace, str) else new_trace
                    # Idempotency check: don't append if a trace for this article_hash already exists
                    if not any(t.get("article_hash") == new_trace_obj.get("article_hash") for t in old_traces):
                        old_traces.append(new_trace_obj)
                new_trace = old_traces
            except: pass
            
        else:
            if new_trace:
                try:
                    new_trace = [json.loads(new_trace) if isinstance(new_trace, str) else new_trace]
                except:
                    new_trace = []
        
        opportunity_score_dict = event_data.get("opportunity_score", {})
        
        # Explicit UPSERT pattern (simulated via REPLACE but preserving appends)
        cursor.execute("""
            INSERT OR REPLACE INTO v4_event_ledger (
                event_id, created_at, updated_at, status, event_type,
                opportunity_score, entity_confidence, event_confidence, trade_confidence, financial_quality,
                confidence_history, hypotheses, validated_trades, evidence, entities, routing_destination, 
                lifecycle, human_review_flag, merge_decision, v2_outcome, event_trace, 
                article_hash, v4_run_id, parent_run_id, v4_outcome
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event_id,
            event_data["created_at"],
            event_data["updated_at"],
            event_data["status"],
            event_data["event_type"],
            json.dumps(opportunity_score_dict),
            opportunity_score_dict.get("entity_confidence"),
            opportunity_score_dict.get("event_confidence"),
            opportunity_score_dict.get("trade_confidence"),
            opportunity_score_dict.get("financial_quality"),
            json.dumps(new_conf),
            json.dumps(event_data.get("hypotheses", [])),
            json.dumps(event_data.get("validated_trades", [])),
            json.dumps(new_evidence),
            json.dumps(event_data.get("entities", [])),
            event_data.get("routing_destination", "SHADOW_NO_SEND"),
            json.dumps(event_data.get("lifecycle", [])),
            event_data.get("human_review_flag", 0),
            json.dumps(event_data.get("merge_decision", {})) if event_data.get("merge_decision") else None,
            json.dumps(event_data.get("v2_outcome", {})),
            json.dumps(new_trace),
            event_data.get("article_hash"),
            event_data.get("v4_run_id"),
            event_data.get("parent_run_id"),
            json.dumps(event_data.get("v4_outcome", {}))
        ))
        conn.commit()
    finally:
        conn.close()

def save_workflow_health(health_data=None):
    conn = _get_connection(DEVOPS_DB_PATH)
    try:
        gmt_now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT")
        funnel_json = json.dumps(health_data.get('funnel', {})) if health_data else "{}"
        
        conn.execute("""
            INSERT OR REPLACE INTO workflow_health (
                timestamp, run_id, total_scanned, articles, errors, drift_score, runtime, funnel_telemetry,
                engine_version, execution_mode, parent_run_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            gmt_now,
            health_data.get('run_id', 'UNKNOWN') if health_data else 'UNKNOWN',
            health_data.get('total_scanned', 0) if health_data else 0,
            health_data.get('articles', 0) if health_data else 0,
            health_data.get('errors', 0) if health_data else 0,
            health_data.get('drift_score', 0.0) if health_data else 0.0,
            health_data.get('runtime', 0.0) if health_data else 0.0,
            funnel_json,
            health_data.get('engine_version', 'V2') if health_data else 'V2',
            health_data.get('execution_mode', 'LIVE') if health_data else 'LIVE',
            health_data.get('parent_run_id') if health_data else None
        ))
        conn.commit()
    except Exception as e:
        logger.error(f"[DB FAULT] Failed to save workflow health: {e}")
    finally:
        conn.close()

def save_exception_log(*args, **kwargs): pass
def save_source_stats(*args, **kwargs): pass

def log_audit_source_metrics(run_id: str, ledger: list):
    conn = _get_connection(AUDIT_DB_PATH)
    try:
        gmt_now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT")
        for entry in ledger:
            meta = entry.get("metadata", {})
            try:
                conn.execute("""
                    INSERT INTO daily_source_metrics 
                    (run_id, timestamp, source, channel, raw_found, unique_found, pages_visited, page_limit, checkpoint_found, emergency_stop, reason,
                     valid_url_count, valid_title_count, valid_body_count, entered_dedupe_count, dedupe_passed_count, dedupe_rejected_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    run_id, gmt_now, entry.get("source"), entry.get("channel", "UNKNOWN"),
                    entry.get("articles_scanned", 0), entry.get("unique_found", 0),
                    meta.get("pages_visited", 0), meta.get("page_limit", 0),
                    meta.get("checkpoint_found", False), meta.get("emergency_stop", False), meta.get("reason", ""),
                    entry.get("valid_url_count", 0), entry.get("valid_title_count", 0), entry.get("valid_body_count", 0),
                    entry.get("entered_dedupe_count", 0), entry.get("dedupe_passed_count", 0), entry.get("dedupe_rejected_count", 0)
                ))
            except Exception as row_err:
                logger.error(f"[DB FAULT] Failed to write daily_source_metrics row for {entry.get('source')}: {row_err} - Data: {entry}")
        conn.commit()
    except Exception as e:
        logger.error(f"[DB FAULT] Failed to write daily_source_metrics: {e}")
    finally:
        conn.close()

def log_audit_ai_metrics(run_id: str, telemetry: list):
    conn = _get_connection(AUDIT_DB_PATH)
    try:
        gmt_now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT")
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
    except Exception as e:
        logger.error(f"[DB FAULT] Failed to write daily_ai_metrics: {e}")
    finally:
        conn.close()

def log_audit_event(run_id: str, source_or_provider: str, event_type: str, severity: str, details: str):
    """Writes a black-box event log directly to the audit database."""
    conn = _get_connection(AUDIT_DB_PATH)
    try:
        gmt_now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT")
        conn.execute("""
            INSERT INTO audit_events 
            (timestamp, run_id, source_or_provider, event_type, severity, details)
            VALUES (?, ?, ?, ?, ?, ?);
        """, (
            gmt_now, run_id, source_or_provider, event_type, severity, details
        ))
        conn.commit()
    except Exception as e:
        logger.error(f"[DB FAULT] Failed to write audit event: {e}")
    finally:
        conn.close()

def log_email_dispatch(event_id: str, decision_id: str, recipient: str, smtp_host: str, smtp_port: int, attempt_number: int, outcome_state: str, exception_class: str = None, exception_message: str = None, provider_response: str = None):
    conn = _get_connection(AUDIT_DB_PATH)
    try:
        gmt_now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT")
        conn.execute("""
            INSERT INTO email_dispatch_log 
            (event_id, decision_id, timestamp, recipient, smtp_host, smtp_port, attempt_number, outcome_state, exception_class, exception_message, provider_response)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            event_id, decision_id, gmt_now, recipient, smtp_host, smtp_port, attempt_number, outcome_state, exception_class, exception_message, provider_response
        ))
        conn.commit()
    except Exception as e:
        logger.error(f"[DB FAULT] Failed to log email dispatch state {outcome_state}: {e}")
    finally:
        conn.close()