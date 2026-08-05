import json
import sqlite3
import os

DB_PATH = "ssr_observability.db"

def _dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def _get_connection():
    if not os.path.exists(DB_PATH):
        pass
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = _dict_factory
    return conn

def export_archive_json(filepath="docs/archive_data.json"):
    """
    Exports the complete history of SSR 2.0 Decisions into the JSON format
    consumed by the Evidence Engine's HTML Dashboards.
    """
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        manifests = []
        try:
            cursor.execute("""
                SELECT 
                    e.decision_id, 
                    e.event_id, 
                    e.manifest_hash, 
                    e.runtime_timestamp, 
                    e.detection_outcome, 
                    e.terminal_stage, 
                    e.ontology_metadata,
                    e.execution_timings,
                    f.headline, 
                    f.source_url as url
                FROM evaluation_ledger e
                LEFT JOIN factual_metadata f ON e.decision_id = f.decision_id
                ORDER BY e.runtime_timestamp DESC
                LIMIT 2000
            """)
            rows = cursor.fetchall()
            for r in rows:
                try:
                    ontology_meta = json.loads(r.get("ontology_metadata") or "{}")
                except Exception:
                    ontology_meta = {}
                    
                try:
                    execution_timings = json.loads(r.get("execution_timings") or "{}")
                except Exception:
                    execution_timings = {}

                manifests.append({
                    "manifest_registry": {
                        "decision_id": r["decision_id"],
                        "event_id": r["event_id"],
                        "configuration_manifest_hash": r["manifest_hash"],
                        "execution_timestamp_gmt": r["runtime_timestamp"],
                        "evidence_completeness_score": 1.0
                    },
                    "detection_vector": {
                        "outcome": r["detection_outcome"],
                        "terminal_stage": r["terminal_stage"],
                        "detected_event_type": "Corporate Announcement",
                        "target_ticker": "UNKNOWN",
                        "confidence_decomposition": {
                            "aggregate_confidence": 1.0
                        }
                    },
                    "ontology_metadata": ontology_meta,
                    "performance_telemetry_ms": execution_timings,
                    "syndication_lineage": {"canonical_sensor_id": "System"},
                    "timestamp": r["runtime_timestamp"],
                    "outcome": r["detection_outcome"],
                    "pipeline_stage": r["terminal_stage"],
                    "headline": r.get("headline", ""),
                    "url": r.get("url", "")
                })
        except sqlite3.OperationalError as e:
            print(f"[EXPORT WARN] Could not query evaluation_ledger: {e}")

        conn.close()

        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump({"ledger": manifests}, f, indent=2)

        print(f"[EXPORT] Successfully wrote {len(manifests)} Decision Manifests to {filepath}")
        return True

    except Exception as e:
        print(f"[EXPORT ERROR] Failed to generate archive_data.json: {e}")
        return False


def export_screening_log(filepath="docs/screening_log.json", limit=20000):
    """
    Exports the most recent N screened articles (passed AND dropped) so the
    dashboard can show exactly what the pipeline looked at and what happened to it.
    """
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        
        rows = []
        try:
            cursor.execute("""
                SELECT id, run_id, timestamp, headline, url, source, outcome, final_stage, drop_reason, ticker, event_family, ingestion_mode
                FROM article_screening_log
                ORDER BY timestamp DESC, id DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
        except sqlite3.OperationalError as e:
            print(f"[EXPORT WARN] Could not query article_screening_log: {e}")
            
        conn.close()

        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({"screening_log": rows}, f, indent=2)

        print(f"[EXPORT] Successfully wrote {len(rows)} screening log entries to {filepath}")
        return True
    except Exception as e:
        print(f"[EXPORT ERROR] Failed to generate screening_log.json: {e}")
        return False

# Export wrapper for backward compatibility in case monitor.py tries to import export_screening_json
export_screening_json = export_screening_log

if __name__ == "__main__":
    export_archive_json()
    export_screening_log()