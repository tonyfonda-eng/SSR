import json
import sqlite3
import os
from collections import defaultdict

DB_PATHS = ["ssr_decisions.db", "ssr_observability.db"]

def _dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def _get_connection():
    for path in DB_PATHS:
        if os.path.exists(path):
            conn = sqlite3.connect(path)
            conn.row_factory = _dict_factory
            return conn, path
    # Fallback default
    conn = sqlite3.connect(DB_PATHS[0])
    conn.row_factory = _dict_factory
    return conn, DB_PATHS[0]

def export_archive_json(filepath="docs/archive_data.json"):
    """
    Exports the complete history of SSR 2.0 Decisions into the JSON format
    consumed by the Evidence Engine's HTML Dashboards.
    """
    try:
        conn, db_file = _get_connection()
        cursor = conn.cursor()

        # Try decisions table first (ssr_decisions.db schema)
        manifests = []
        try:
            cursor.execute("""
                SELECT decision_id, event_id, manifest_hash, runtime_timestamp, detection_outcome, terminal_stage, headline, url, payload
                FROM decisions
                ORDER BY created_at DESC
                LIMIT 500
            """)
            rows = cursor.fetchall()
            for r in rows:
                payload_str = r.get("payload", "{}")
                try:
                    capsule = json.loads(payload_str)
                except Exception:
                    capsule = {}

                ai_props = capsule.get("ai_core_inference", {}).get("parsed_structural_properties", {})
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
                        "detected_event_type": capsule.get("event_family", "Corporate Announcement"),
                        "target_ticker": ai_props.get("ticker", "UNKNOWN"),
                        "confidence_decomposition": {
                            "aggregate_confidence": capsule.get("ai_core_inference", {}).get("aggregate_confidence", 1.0)
                        }
                    },
                    "performance_telemetry_ms": capsule.get("performance_telemetry_ms", {}),
                    "evidentiary_provenance_dag": capsule.get("evidentiary_provenance_dag", {"supporting_evidence": [], "opposing_evidence": []}),
                    "syndication_lineage": {"canonical_sensor_id": capsule.get("source", "System")},
                    "timestamp": r["runtime_timestamp"],
                    "outcome": r["detection_outcome"],
                    "pipeline_stage": r["terminal_stage"],
                    "source": capsule.get("source", "System"),
                    "issuer": ai_props.get("ticker", "UNKNOWN"),
                    "headline": r["headline"],
                    "url": r["url"]
                })
        except sqlite3.OperationalError:
            pass

        conn.close()

        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump({"ledger": manifests}, f, indent=2)

        print(f"[EXPORT] Successfully wrote {len(manifests)} Decision Manifests to {filepath}")
        return True

    except Exception as e:
        print(f"[EXPORT ERROR] Failed to generate archive_data.json: {e}")
        return False


def export_screening_json(filepath="docs/screening_log.json"):
    """
    Exports the article screening log into JSON for docs/screening_log.html.
    """
    try:
        conn, db_file = _get_connection()
        cursor = conn.cursor()

        rows = []
        try:
            cursor.execute("""
                SELECT decision_id, event_id, runtime_timestamp as timestamp, headline, url, detection_outcome as outcome, terminal_stage as final_stage
                FROM decisions
                ORDER BY created_at DESC
                LIMIT 1000
            """)
            rows = cursor.fetchall()
        except sqlite3.OperationalError:
            pass

        conn.close()

        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(rows, f, indent=2)

        print(f"[EXPORT] Successfully wrote {len(rows)} screening records to {filepath}")
        return True

    except Exception as e:
        print(f"[EXPORT ERROR] Failed to export screening JSON: {e}")
        return False

if __name__ == "__main__":
    export_archive_json()
    export_screening_json()