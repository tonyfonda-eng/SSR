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
import uuid
import sys

logger = logging.getLogger(__name__)

# Strict physical isolation of storage domains
RESEARCH_DB_PATH = "ssr_observability.db"
DEVOPS_DB_PATH = "ssr_devops.db"
# Backwards-compatible alias expected by other modules
DB_PATH = RESEARCH_DB_PATH

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

    # DEVOPS DB
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

    initialise_database = init_db

# -------------------------------------------------------------------------
# CORE REPO INTERFACES (Facts Layer & Context Manifest Processing)
# -------------------------------------------------------------------------


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
    except Exception as e:
        logger.warning(f"[DB FAULT] Unable to retrieve config snapshot: {e}")
        return None

# MODULE-LEVEL EXPORTS REQUIRED BY MONITOR.PY
def initialise_database():
    init_db()

# -------------------------------------------------------------------------
# Added implementations to satisfy monitor.py expectations
# -------------------------------------------------------------------------

def _now_ts():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT")


def get_or_create_event(article_hash: str, raw_payload_blob: bytes):
    """
    Idempotently ensures an event exists for a given article_hash.
    Returns (event_id, is_new).
    """
    try:
        conn = sqlite3.connect(RESEARCH_DB_PATH)
        conn.execute("PRAGMA foreign_keys = ON;")
        cursor = conn.cursor()
        cursor.execute("SELECT event_id FROM event_registry WHERE article_hash = ?", (article_hash,))
        row = cursor.fetchone()
        if row:
            conn.close()
            return row[0], False

        # Create a deterministic event id based on hash + uuid
        event_id = f"EVT-{hashlib.sha256((article_hash + str(uuid.uuid4())).encode('utf-8')).hexdigest()[:12].upper()}"
        ingest_ts = _now_ts()
        cursor.execute(
            "INSERT INTO event_registry (event_id, article_hash, raw_payload_blob, payload_mime_type, ingest_timestamp) VALUES (?, ?, ?, ?, ?)",
            (event_id, article_hash, sqlite3.Binary(raw_payload_blob if raw_payload_blob is not None else b""), "application/octet-stream", ingest_ts)
        )
        conn.commit()
        conn.close()
        return event_id, True
    except Exception as e:
        logger.error(f"[DB ERROR] get_or_create_event failed: {e}")
        try:
            conn.close()
        except Exception:
            pass
        raise


def commit_decision_capsule(decision: dict):
    """
    Persists a decision/alert into the normalized evaluation_ledger and related tables.
    Expects at minimum keys: decision_id, event_id, manifest_hash, runtime_timestamp, detection_outcome, terminal_stage
    """
    try:
        conn = sqlite3.connect(RESEARCH_DB_PATH)
        conn.execute("PRAGMA foreign_keys = ON;")
        cursor = conn.cursor()

        decision_id = decision.get("decision_id")
        event_id = decision.get("event_id")
        manifest_hash = decision.get("manifest_hash")
        runtime_timestamp = decision.get("runtime_timestamp", _now_ts())
        detection_outcome = decision.get("detection_outcome", "UNKNOWN")
        terminal_stage = decision.get("terminal_stage", "UNKNOWN")
        evidence_completeness_score = float(decision.get("evidence_completeness_score", 1.0))
        parent_decision_id = decision.get("parent_decision_id")
        market_snapshot = json.dumps(decision.get("market_data_snapshot")) if decision.get("market_data_snapshot") is not None else None

        cursor.execute(
            "INSERT OR REPLACE INTO evaluation_ledger (decision_id, event_id, manifest_hash, runtime_timestamp, detection_outcome, terminal_stage, evidence_completeness_score, parent_decision_id, market_data_snapshot) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (decision_id, event_id, manifest_hash, runtime_timestamp, detection_outcome, terminal_stage, evidence_completeness_score, parent_decision_id, market_snapshot)
        )

        # factual_metadata
        try:
            headline = decision.get("headline")
            source_url = decision.get("url") or decision.get("source_url")
            published_ts = decision.get("published_timestamp") or runtime_timestamp
            if headline or source_url:
                cursor.execute(
                    "INSERT OR REPLACE INTO factual_metadata (decision_id, headline, source_url, published_timestamp) VALUES (?, ?, ?, ?)",
                    (decision_id, headline, source_url, published_ts)
                )
        except Exception:
            # non-critical
            logger.debug("factual_metadata insert skipped or failed")

        # ai_core_inference
        try:
            ai = decision.get("ai_core_inference") or {}
            raw_provider_json = json.dumps(ai)
            parsed_structural = json.dumps(ai.get("parsed_structural_properties")) if ai.get("parsed_structural_properties") is not None else None
            aggregate_confidence = float(ai.get("aggregate_confidence", 1.0))
            cursor.execute(
                "INSERT OR REPLACE INTO ai_core_inference (decision_id, raw_provider_json, parsed_structural_properties, aggregate_confidence) VALUES (?, ?, ?, ?)",
                (decision_id, raw_provider_json, parsed_structural, aggregate_confidence)
            )
        except Exception:
            logger.debug("ai_core_inference insert skipped or failed")

        conn.commit()
        conn.close()
        logger.info(f"[DB] Committed decision {decision_id}")
    except Exception as e:
        logger.error(f"[DB ERROR] commit_decision_capsule failed: {e}")
        try:
            conn.close()
        except Exception:
            pass
        raise


def save_workflow_health(payload: dict):
    """
    Saves a compact run-level health payload to the devops DB.
    """
    try:
        conn = sqlite3.connect(DEVOPS_DB_PATH)
        cursor = conn.cursor()
        ts = _now_ts()
        cursor.execute(
            "INSERT OR REPLACE INTO workflow_health (timestamp, run_id, total_scanned, articles, errors, drift_score, runtime, failed, succeeded, skipped, git_commit, branch, python_version, exception, workflow_version, run_number) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                ts,
                payload.get("run_id"),
                int(payload.get("total_scanned", 0)),
                int(payload.get("articles", 0)),
                int(payload.get("errors", 0)),
                float(payload.get("drift_score", 0.0)),
                float(payload.get("runtime", 0.0)),
                int(payload.get("failed", 0)),
                int(payload.get("succeeded", 0)),
                int(payload.get("skipped", 0)),
                payload.get("git_commit"),
                payload.get("branch"),
                sys.version,
                payload.get("exception"),
                payload.get("workflow_version"),
                payload.get("run_number")
            )
        )
        conn.commit()
        conn.close()
        logger.info("[DB] Workflow health saved")
    except Exception as e:
        logger.error(f"[DB ERROR] save_workflow_health failed: {e}")
        try:
            conn.close()
        except Exception:
            pass
        raise


def save_exception_log(run_id: str, exc_type: str = None, stack_trace: str = None, module: str = None, func_name: str = None, article_url: str = None, severity: str = "ERROR"):
    """
    Persists an exception entry into the devops exception_logs table.
    """
    try:
        conn = sqlite3.connect(DEVOPS_DB_PATH)
        cursor = conn.cursor()
        ts = _now_ts()
        cursor.execute(
            "INSERT INTO exception_logs (run_id, timestamp, exc_type, stack_trace, module, func_name, article_url, severity) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (run_id, ts, exc_type, stack_trace, module, func_name, article_url, severity)
        )
        conn.commit()
        conn.close()
        logger.info("[DB] Exception logged")
    except Exception as e:
        logger.error(f"[DB ERROR] save_exception_log failed: {e}")
        try:
            conn.close()
        except Exception:
            pass
        raise


def save_config_snapshot(manifest_hash: str, run_id: str, config_json: str):
    """
    Writes a captured configuration snapshot into the research DB.
    """
    try:
        conn = sqlite3.connect(RESEARCH_DB_PATH)
        cursor = conn.cursor()
        ts = _now_ts()
        cursor.execute(
            "INSERT OR REPLACE INTO config_snapshots (hash, captured_at, run_id, config_json) VALUES (?, ?, ?, ?)",
            (manifest_hash, ts, run_id, config_json)
        )
        conn.commit()
        conn.close()
        logger.info(f"[DB] Config snapshot {manifest_hash} saved")
    except Exception as e:
        logger.error(f"[DB ERROR] save_config_snapshot failed: {e}")
        try:
            conn.close()
        except Exception:
            pass
        raise
