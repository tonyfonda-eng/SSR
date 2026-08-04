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
    
    # Phase 1: Configuration Manifest Snapshots
    r_conn.execute("""
        CREATE TABLE IF NOT EXISTS config_snapshots (
            hash TEXT PRIMARY KEY,
            captured_at TEXT NOT NULL,
            run_id TEXT NOT NULL,
            config_json TEXT NOT NULL
        );
    """)

    # Legacy Configuration tracking (kept for backward compatibility during transition)
    r_conn.execute("""
        CREATE TABLE IF NOT EXISTS configuration_manifests (
            manifest_hash TEXT PRIMARY KEY,
            parser_version TEXT NOT NULL,
            transformation_dag_version TEXT NOT NULL,
            ontology_version TEXT NOT NULL,
            rule_pack_version TEXT NOT NULL,
            prompt_version TEXT NOT NULL,
            playbook_version TEXT NOT NULL
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
        CREATE TABLE IF NOT EXISTS sensor_assets (
            sensor_id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            data_format TEXT NOT NULL,
            coverage_scope TEXT,
            estimated_annual_cost REAL DEFAULT 0.0,
            known_blind_spots TEXT,
            maintenance_notes TEXT
        );
    """)

    r_conn.execute("""
        CREATE TABLE IF NOT EXISTS sensor_lineage (
            lineage_id TEXT PRIMARY KEY,
            event_id TEXT NOT NULL,
            sensor_id TEXT NOT NULL,
            wire_published_timestamp TEXT,
            canonical_source_url TEXT NOT NULL,
            FOREIGN KEY (event_id) REFERENCES event_registry(event_id),
            FOREIGN KEY (sensor_id) REFERENCES sensor_assets(sensor_id)
        );
    """)

    r_conn.execute("""
        CREATE TABLE IF NOT EXISTS evidence_transformations (
            transformation_id TEXT PRIMARY KEY,
            event_id TEXT NOT NULL,
            stage_name TEXT NOT NULL,
            transformation_version TEXT NOT NULL,
            output_hash TEXT NOT NULL,
            duration_ms INTEGER NOT NULL,
            transformed_payload TEXT NOT NULL,
            FOREIGN KEY (event_id) REFERENCES event_registry(event_id)
        );
    """)

    # Core Evaluation Ledger
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
            FOREIGN KEY (event_id) REFERENCES event_registry(event_id),
            FOREIGN KEY (parent_decision_id) REFERENCES evaluation_ledger(decision_id)
        );
    """)

    # Attempt to gracefully alter the table if it exists but is missing the new column (Phase 1 Migration)
    try:
        r_conn.execute("ALTER TABLE evaluation_ledger ADD COLUMN market_data_snapshot TEXT;")
    except sqlite3.OperationalError:
        pass # Column already exists

    r_conn.execute("""
        CREATE TABLE IF NOT EXISTS execution_performance (
            decision_id TEXT PRIMARY KEY,
            ingest_repo_ms INTEGER NOT NULL,
            transformation_ms INTEGER NOT NULL,
            ontology_ms INTEGER NOT NULL,
            rules_ms INTEGER NOT NULL,
            ai_inference_ms INTEGER NOT NULL,
            financial_query_ms INTEGER NOT NULL,
            FOREIGN KEY (decision_id) REFERENCES evaluation_ledger(decision_id)
        );
    """)

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
            text_start_offset INTEGER,
            text_end_offset INTEGER,
            FOREIGN KEY (decision_id) REFERENCES evaluation_ledger(decision_id),
            FOREIGN KEY (source_transformation_id) REFERENCES evidence_transformations(transformation_id)
        );
    """)

    r_conn.execute("""
        CREATE TABLE IF NOT EXISTS ai_core_inference (
            decision_id TEXT PRIMARY KEY,
            raw_provider_json TEXT NOT NULL,
            parsed_structural_properties TEXT,
            semantic_interpretation TEXT,
            ontology_confidence REAL,
            rules_confidence REAL,
            ai_confidence REAL,
            financial_confidence REAL,
            aggregate_confidence REAL NOT NULL,
            FOREIGN KEY (decision_id) REFERENCES evaluation_ledger(decision_id)
        );
    """)

    r_conn.execute("""
        CREATE TABLE IF NOT EXISTS human_overrides (
            override_id TEXT PRIMARY KEY,
            decision_id TEXT NOT NULL,
            reviewer_identity TEXT NOT NULL,
            override_timestamp TEXT NOT NULL,
            previous_decision TEXT NOT NULL,
            validated_decision TEXT NOT NULL,
            override_rationale_text TEXT NOT NULL,
            FOREIGN KEY (decision_id) REFERENCES evaluation_ledger(decision_id)
        );
    """)
    
    r_conn.commit()
    r_conn.close()

    # -------------------------------------------------------------------------
    # 2. DEVOPS & INFRASTRUCTURE LOGS
    # -------------------------------------------------------------------------
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
            runtime REAL NOT NULL,
            failed INTEGER NOT NULL DEFAULT 0,
            succeeded INTEGER NOT NULL DEFAULT 0,
            skipped INTEGER NOT NULL DEFAULT 0,
            git_commit TEXT,
            branch TEXT,
            python_version TEXT,
            exception TEXT,
            workflow_version TEXT,
            run_number TEXT
        );
    """)

    d_conn.execute("""
        CREATE TABLE IF NOT EXISTS exception_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT,
            timestamp TEXT NOT NULL,
            exc_type TEXT,
            stack_trace TEXT,
            module TEXT,
            func_name TEXT,
            article_url TEXT,
            severity TEXT
        );
    """)

    d_conn.execute("""
        CREATE TABLE IF NOT EXISTS ai_usage_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT,
            timestamp TEXT NOT NULL,
            provider TEXT NOT NULL,
            key_id TEXT,
            requests INTEGER DEFAULT 0,
            success INTEGER DEFAULT 0,
            failures INTEGER DEFAULT 0,
            errors_429 INTEGER DEFAULT 0,
            errors_503 INTEGER DEFAULT 0,
            timeouts INTEGER DEFAULT 0,
            retries INTEGER DEFAULT 0,
            fallbacks INTEGER DEFAULT 0,
            response_time_sum REAL DEFAULT 0.0,
            max_latency REAL DEFAULT 0.0,
            last_success_ts TEXT,
            last_failure_ts TEXT
        );
    """)

    d_conn.execute("""
        CREATE TABLE IF NOT EXISTS source_stats_log (
            run_id TEXT,
            timestamp TEXT NOT NULL,
            source TEXT NOT NULL,
            downloaded INTEGER DEFAULT 0,
            survived_regex INTEGER DEFAULT 0,
            survived_ontology INTEGER DEFAULT 0,
            survived_rules INTEGER DEFAULT 0,
            reached_ai INTEGER DEFAULT 0,
            alerts INTEGER DEFAULT 0,
            processing_time_sum REAL DEFAULT 0.0,
            processed_count INTEGER DEFAULT 0,
            PRIMARY KEY (run_id, source)
        );
    """)

    d_conn.execute("""
        CREATE TABLE IF NOT EXISTS dashboard_state_kv (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)

    d_conn.commit()
    d_conn.close()

def initialise_database():
    init_db()

# -------------------------------------------------------------------------
# CORE REPO INTERFACES (Facts Layer & Context Manifest Processing)
# -------------------------------------------------------------------------

def get_latest_config_snapshot() -> dict:
    """Retrieves the most recent config hash snapshot to evaluate diffs."""
    try:
        conn = sqlite3.connect(RESEARCH_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT hash, captured_at, run_id, config_json FROM config_snapshots ORDER BY captured_at DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        if row:
            return {"hash": row[0], "captured_at": row[1], "run_id": row[2], "config_json": row[3]}
        return None
    except Exception as e:
        logger.warning(f"[DB FAULT] Unable to retrieve config snapshot: {e}")
        return None

def save_config_snapshot(config_hash: str, run_id: str, config_json: str):
    """Persists a new immutable configuration JSON snapshot."""
    try:
        gmt_now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT")
        conn = sqlite3.connect(RESEARCH_DB_PATH)
        conn.execute("""
            INSERT OR IGNORE INTO config_snapshots (hash, captured_at, run_id, config_json)
            VALUES (?, ?, ?, ?);
        """, (config_hash, gmt_now, run_id, config_json))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"[SCHEMA ERROR] save_config_snapshot failed: {e}")


def generate_manifest_hash(components: dict) -> str:
    """Computes a strict content-addressed SHA256 signature from system version maps."""
    serialized = json.dumps(components, sort_keys=True).encode("utf-8")
    return f"CFG-{hashlib.sha256(serialized).hexdigest()[:12].upper()}"


def register_configuration_manifest(manifest_data: dict) -> str:
    """Freezes an environment lineage profile in the configuration tracking table."""
    m_hash = generate_manifest_hash(manifest_data)
    try:
        conn = sqlite3.connect(RESEARCH_DB_PATH)
        conn.execute("""
            INSERT OR IGNORE INTO configuration_manifests 
            (manifest_hash, parser_version, transformation_dag_version, ontology_version, rule_pack_version, prompt_version, playbook_version)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (
            m_hash,
            manifest_data.get("parser_version", "1.0.0"),
            manifest_data.get("transformation_dag_version", "1.0.0"),
            manifest_data.get("ontology_version", "1.0.0"),
            manifest_data.get("rule_pack_version", "1.0.0"),
            manifest_data.get("prompt_version", "1.0.0"),
            manifest_data.get("playbook_version", "1.0.0")
        ))
        conn.commit()
        conn.close()
        return m_hash
    except Exception as e:
        return m_hash


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
        cursor.execute("""
            INSERT INTO event_registry (event_id, article_hash, raw_payload_blob, payload_mime_type, ingest_timestamp)
            VALUES (?, ?, ?, ?, ?);
        """, (event_id, article_hash, sqlite3.Binary(raw_payload), mime_type, gmt_now))
        conn.commit()
        conn.close()
        return event_id, True
    except Exception as e:
        conn.close()
        return f"ERR-{event_id}", True


def log_sensor_lineage(event_id: str, sensor_id: str, url: str, wire_ts: str):
    gmt_now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT")
    lineage_id = f"LIN-{hashlib.sha256(f'{event_id}:{sensor_id}:{gmt_now}'.encode('utf-8')).hexdigest()[:12].upper()}"
    try:
        conn = sqlite3.connect(RESEARCH_DB_PATH)
        conn.execute("""
            INSERT OR IGNORE INTO sensor_lineage (lineage_id, event_id, sensor_id, wire_published_timestamp, canonical_source_url)
            VALUES (?, ?, ?, ?, ?);
        """, (lineage_id, event_id, sensor_id, wire_ts or gmt_now, url))
        conn.commit()
        conn.close()
    except Exception:
        pass


def log_transformation(event_id: str, stage: str, version: str, text_payload: str, duration_ms: int) -> str:
    output_hash = hashlib.sha256(text_payload.encode("utf-8")).hexdigest()
    trn_id = f"TRN-{hashlib.md5(f'{event_id}:{stage}:{output_hash}'.encode('utf-8')).hexdigest()[:12].upper()}"
    try:
        conn = sqlite3.connect(RESEARCH_DB_PATH)
        conn.execute("""
            INSERT OR REPLACE INTO evidence_transformations (transformation_id, event_id, stage_name, transformation_version, output_hash, duration_ms, transformed_payload)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (trn_id, event_id, stage, version, output_hash, duration_ms, text_payload))
        conn.commit()
        conn.close()
        return trn_id
    except Exception:
        return "TRN-FALLBACK"

def commit_decision_capsule(capsule_data: dict, manifest_json: dict = None):
    try:
        conn = sqlite3.connect(RESEARCH_DB_PATH)
        cursor = conn.cursor()
        dec_id = capsule_data["decision_id"]
        
        cursor.execute("""
            INSERT OR REPLACE INTO evaluation_ledger 
            (decision_id, event_id, manifest_hash, runtime_timestamp, detection_outcome, terminal_stage, evidence_completeness_score, parent_decision_id, market_data_snapshot)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            dec_id,
            capsule_data["event_id"],
            capsule_data["manifest_hash"],
            capsule_data.get("runtime_timestamp", datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT")),
            capsule_data["detection_outcome"],
            capsule_data["terminal_stage"],
            capsule_data.get("evidence_completeness_score", 1.0),
            capsule_data.get("parent_decision_id"),
            capsule_data.get("market_data_snapshot")
        ))
        
        perf = capsule_data.get("performance_telemetry_ms", {})
        cursor.execute("""
            INSERT OR REPLACE INTO execution_performance 
            (decision_id, ingest_repo_ms, transformation_ms, ontology_ms, rules_ms, ai_inference_ms, financial_query_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (
            dec_id,
            perf.get("ingest_repo_ms", 0),
            perf.get("transformation_ms", 0),
            perf.get("ontology_ms", 0),
            perf.get("rules_ms", 0),
            perf.get("ai_inference_ms", 0),
            perf.get("financial_query_ms", 0)
        ))
        
        evidence_list = capsule_data.get("evidence_provenance_ledger", [])
        for ev in evidence_list:
            cursor.execute("""
                INSERT OR REPLACE INTO atomic_evidence 
                (evidence_id, decision_id, stage, evidence_direction, source_component, assertion_key, confidence_weight, source_transformation_id, text_start_offset, text_end_offset)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                ev["evidence_id"],
                dec_id,
                ev["stage"],
                ev["evidence_direction"],
                ev["source_component"],
                ev["assertion_key"],
                ev["confidence_weight"],
                ev.get("source_transformation_id"),
                ev.get("text_start_offset"),
                ev.get("text_end_offset")
            ))
            
        ai_data = capsule_data.get("ai_core_inference", {})
        if ai_data:
            conf = ai_data.get("confidence_decomposition", {})
            cursor.execute("""
                INSERT OR REPLACE INTO ai_core_inference 
                (decision_id, raw_provider_json, parsed_structural_properties, semantic_interpretation, ontology_confidence, rules_confidence, ai_confidence, financial_confidence, aggregate_confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                dec_id,
                ai_data.get("raw_provider_json", "{}"),
                json.dumps(ai_data.get("parsed_structural_properties", {})),
                ai_data.get("semantic_interpretation", ""),
                conf.get("ontology_score", 0.0),
                conf.get("rules_score", 0.0),
                conf.get("ai_node", 0.0),
                conf.get("financial_node", 0.0),
                ai_data.get("aggregate_confidence", 0.0)
            ))
            
        if manifest_json:
            manifest_str = json.dumps(manifest_json)
            d_conn = sqlite3.connect(DEVOPS_DB_PATH)
            d_conn.execute("INSERT OR REPLACE INTO dashboard_state_kv (key, value) VALUES (?, ?);", 
                           (f"MANIFEST:{dec_id}", manifest_str))
            d_conn.commit()
            d_conn.close()

        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"[CRITICAL DATA FLUSH FAULT] Capsule transactional commit failed: {e}")

def save_workflow_health(health_data=None):
    try:
        gmt_now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT")
        conn = sqlite3.connect(DEVOPS_DB_PATH)
        conn.execute("""
            INSERT OR REPLACE INTO workflow_health (timestamp, run_id, total_scanned, articles, errors, drift_score, runtime, failed, succeeded, skipped, git_commit, branch, python_version, exception, workflow_version, run_number)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            gmt_now,
            health_data.get('run_id', 'UNKNOWN') if health_data else 'UNKNOWN',
            health_data.get('total_scanned', 0) if health_data else 0,
            health_data.get('articles', 0) if health_data else 0,
            health_data.get('errors', 0) if health_data else 0,
            health_data.get('drift_score', 0.0) if health_data else 0.0,
            health_data.get('runtime', 0.0) if health_data else 0.0,
            health_data.get('failed', 0) if health_data else 0,
            health_data.get('succeeded', 0) if health_data else 0,
            health_data.get('skipped', 0) if health_data else 0,
            health_data.get('git_commit', 'unknown'),
            health_data.get('branch', 'unknown'),
            health_data.get('python_version', 'unknown'),
            health_data.get('exception', ''),
            health_data.get('workflow_version', '2.0'),
            health_data.get('run_number', '1')
        ))
        conn.commit()
        conn.close()
    except Exception:
        pass

def save_exception_log(run_id="UNKNOWN", timestamp=None, exc_type="", stack_trace="", module="", func_name="", article_url="", severity="ERROR"):
    try:
        gmt_now = timestamp or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT")
        conn = sqlite3.connect(DEVOPS_DB_PATH)
        conn.execute("""
            INSERT INTO exception_logs (run_id, timestamp, exc_type, stack_trace, module, func_name, article_url, severity)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, (run_id, gmt_now, exc_type, stack_trace, module, func_name, article_url, severity))
        conn.commit()
        conn.close()
    except Exception:
        pass

def save_ai_usage(rows):
    try:
        conn = sqlite3.connect(DEVOPS_DB_PATH)
        conn.executemany("""
            INSERT INTO ai_usage_log (run_id, timestamp, provider, key_id, requests, success, failures, errors_429, errors_503, timeouts, retries, fallbacks, response_time_sum, max_latency, last_success_ts, last_failure_ts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, rows)
        conn.commit()
        conn.close()
    except Exception:
        pass

def save_source_stats(rows):
    try:
        conn = sqlite3.connect(DEVOPS_DB_PATH)
        conn.executemany("""
            INSERT OR REPLACE INTO source_stats_log (run_id, timestamp, source, downloaded, survived_regex, survived_ontology, survived_rules, reached_ai, alerts, processing_time_sum, processed_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, rows)
        conn.commit()
        conn.close()
    except Exception:
        pass

# Backward compatibility stubs
def article_exists(identifier): return False
def save_article(**kwargs): pass
def save_lifecycle_logs(logs): pass
def get_recent_lifecycle_logs(limit=50): return []
def get_dashboard_state(key): return None
def set_dashboard_state(key, value): pass
def track_company(ticker): pass
def create_event_if_new(event_family, ticker): return f"{ticker}_{event_family}", True
def get_pending_reminders(): return []
def mark_reminder_sent(*args, **kwargs): pass
def save_reminder(*args, **kwargs): pass
def perform_housekeeping(): pass
def log_research(*args, **kwargs): pass
def get_30_day_average(): return 0.0
def get_30_day_source_averages(): return {}
def export_archive_json(filepath): pass
def generate_archive_html(*args, **kwargs): pass