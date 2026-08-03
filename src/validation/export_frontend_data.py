import json
import sqlite3
import os
from collections import defaultdict
import datetime

RESEARCH_DB_PATH = "ssr_observability.db"

def _dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def _decode_json(val, default=None):
    if not val:
        return default if default is not None else {}
    try:
        return json.loads(val)
    except json.JSONDecodeError:
        return default if default is not None else {}

def export_archive_json(filepath="docs/archive_data.json"):
    """
    Exports the complete history of SSR 2.0 Decisions into the JSON format
    consumed by the Evidence Engine's HTML Dashboards.
    """
    try:
        conn = sqlite3.connect(RESEARCH_DB_PATH)
        conn.row_factory = _dict_factory
        cursor = conn.cursor()

        # Join across the normalized schema to reconstruct the Canonical Decision Manifest view
        cursor.execute("""
            SELECT 
                el.decision_id,
                el.event_id,
                el.manifest_hash,
                el.runtime_timestamp,
                el.detection_outcome,
                el.terminal_stage,
                el.evidence_completeness_score,
                fm.headline,
                fm.source_url,
                fm.published_timestamp,
                sl.sensor_id,
                ai.parsed_structural_properties,
                ai.aggregate_confidence,
                ep.ingest_repo_ms,
                ep.transformation_ms,
                ep.ontology_ms,
                ep.rules_ms,
                ep.ai_inference_ms,
                ep.financial_query_ms
            FROM evaluation_ledger el
            LEFT JOIN factual_metadata fm ON el.decision_id = fm.decision_id
            LEFT JOIN sensor_lineage sl ON el.event_id = sl.event_id
            LEFT JOIN ai_core_inference ai ON el.decision_id = ai.decision_id
            LEFT JOIN execution_performance ep ON el.decision_id = ep.decision_id
            ORDER BY el.runtime_timestamp DESC
            LIMIT 500
        """)
        
        decisions = cursor.fetchall()
        
        # We need to fetch the atomic evidence (the DAG) separately and bind it
        # to avoid massive denormalized joins
        cursor.execute("""
            SELECT evidence_id, decision_id, stage, evidence_direction, source_component, assertion_key, confidence_weight, source_transformation_id, text_start_offset, text_end_offset
            FROM atomic_evidence
            WHERE decision_id IN (SELECT decision_id FROM evaluation_ledger ORDER BY runtime_timestamp DESC LIMIT 500)
        """)
        evidence_rows = cursor.fetchall()
        
        conn.close()

        # Group evidence by decision_id
        evidence_by_decision = defaultdict(lambda: {"SUPPORTING": [], "OPPOSING": []})
        for ev in evidence_rows:
            direction = ev["evidence_direction"]
            ev_dict = {
                "evidence_id": ev["evidence_id"],
                "stage": ev["stage"],
                "component": ev["source_component"],
                "assertion": ev["assertion_key"],
                "weight": ev["confidence_weight"],
                "causal_link": {
                    "transformation_id": ev["source_transformation_id"],
                    "text_start_offset": ev["text_start_offset"],
                    "text_end_offset": ev["text_end_offset"]
                }
            }
            evidence_by_decision[ev["decision_id"]][direction].append(ev_dict)

        # Assemble the final manifests
        manifests = []
        for d in decisions:
            parsed_ai = _decode_json(d["parsed_structural_properties"], {})
            ev_dag = evidence_by_decision.get(d["decision_id"], {"SUPPORTING": [], "OPPOSING": []})
            
            manifest = {
                "manifest_registry": {
                    "decision_id": d["decision_id"],
                    "event_id": d["event_id"],
                    "configuration_manifest_hash": d["manifest_hash"],
                    "execution_timestamp_gmt": d["runtime_timestamp"],
                    "evidence_completeness_score": d["evidence_completeness_score"]
                },
                "detection_vector": {
                    "outcome": d["detection_outcome"],
                    "terminal_stage": d["terminal_stage"],
                    "detected_event_type": parsed_ai.get("strategy", "Unknown"),
                    "target_ticker": parsed_ai.get("ticker", "UNKNOWN"),
                    "confidence_decomposition": {
                        "aggregate_confidence": d["aggregate_confidence"] or 0.0
                    }
                },
                "performance_telemetry_ms": {
                    "ingest_repo_ms": d["ingest_repo_ms"],
                    "transformation_ms": d["transformation_ms"],
                    "ontology_ms": d["ontology_ms"],
                    "rules_ms": d["rules_ms"],
                    "ai_inference_ms": d["ai_inference_ms"],
                    "financial_query_ms": d["financial_query_ms"]
                },
                "evidentiary_provenance_dag": {
                    "supporting_evidence": ev_dag["SUPPORTING"],
                    "opposing_evidence": ev_dag["OPPOSING"]
                },
                "syndication_lineage": {
                    "canonical_sensor_id": d["sensor_id"]
                },
                # Flattened properties for easy top-level access by UI
                "timestamp": d["runtime_timestamp"],
                "outcome": d["detection_outcome"],
                "pipeline_stage": d["terminal_stage"],
                "source": d["sensor_id"],
                "issuer": parsed_ai.get("ticker", "UNKNOWN"),
                "headline": d["headline"],
                "url": d["source_url"]
            }
            manifests.append(manifest)

        # Ensure directory exists
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump({"ledger": manifests}, f, indent=2)
            
        print(f"[EXPORT] Successfully wrote {len(manifests)} Decision Manifests to {filepath}")
        return True

    except Exception as e:
        print(f"[EXPORT ERROR] Failed to generate archive_data.json: {e}")
        return False

if __name__ == "__main__":
    export_archive_json()