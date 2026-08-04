"""
SSR 2.0: Golden Dataset Builder
Extracts Google Sheets Gold Standards and historical ledger decisions 
to construct an immutable, version-controlled regression dataset.
"""

import json
import sqlite3
import hashlib
import os
from datetime import datetime, timezone

from src.database import RESEARCH_DB_PATH
from src.sheets import load_gold_standards
from src.config.settings import SHEET_URL

GOLDEN_DATASET_PATH = "src/validation/test_assets/golden_benchmark.json"

def compute_hash(data_dict: dict) -> str:
    """Computes a strict SHA-256 hash of the payload to version the dataset."""
    serialized = json.dumps(data_dict, sort_keys=True).encode("utf-8")
    return f"DS-{hashlib.sha256(serialized).hexdigest()[:12].upper()}"

def build_dataset():
    print("[BUILDER] Constructing Immutable Golden Dataset...")
    
    # 1. Load Sheets Standards
    try:
        gs_sheets = load_gold_standards(SHEET_URL)
    except Exception as e:
        print(f"[WARNING] Could not load gold standards from Sheets: {e}")
        gs_sheets = {}

    cases = []
    
    # 2. Extract Historical Ledger Data (True Positives & True Negatives)
    try:
        conn = sqlite3.connect(RESEARCH_DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        # Grab 25 True Positives (Alerts)
        cur.execute("""
            SELECT el.decision_id, er.article_hash, er.raw_payload_blob, el.detection_outcome, ai.semantic_interpretation
            FROM evaluation_ledger el
            JOIN event_registry er ON el.event_id = er.event_id
            LEFT JOIN ai_core_inference ai ON el.decision_id = ai.decision_id
            WHERE el.detection_outcome IN ('DETECTED', 'DISPATCHED')
            ORDER BY el.runtime_timestamp DESC LIMIT 25
        """)
        for row in cur.fetchall():
            cases.append({
                "case_id": row["decision_id"],
                "article_hash": row["article_hash"],
                "raw_text": row["raw_payload_blob"].decode('utf-8', errors='ignore') if row["raw_payload_blob"] else "",
                "expected_outcome": "DETECTED",
                "expected_strategy": row["semantic_interpretation"] or "Unknown",
                "human_rationale": "Historical True Positive extracted from ledger."
            })
            
        # Grab 25 True Negatives (Dropped after initial ingestion)
        cur.execute("""
            SELECT el.decision_id, er.article_hash, er.raw_payload_blob, el.detection_outcome, el.terminal_stage
            FROM evaluation_ledger el
            JOIN event_registry er ON el.event_id = er.event_id
            WHERE el.detection_outcome = 'DROPPED' AND el.terminal_stage != 'Ingestion'
            ORDER BY el.runtime_timestamp DESC LIMIT 25
        """)
        for row in cur.fetchall():
            cases.append({
                "case_id": row["decision_id"],
                "article_hash": row["article_hash"],
                "raw_text": row["raw_payload_blob"].decode('utf-8', errors='ignore') if row["raw_payload_blob"] else "",
                "expected_outcome": "DROPPED",
                "expected_strategy": "None",
                "human_rationale": f"Historical True Negative (Terminal Stage: {row['terminal_stage']})."
            })
            
        conn.close()
    except Exception as e:
        print(f"[WARNING] Database extraction failed: {e}")

    # 3. Assemble and Hash
    payload_to_hash = {"gold_standards_reference": gs_sheets, "cases": cases}
    dataset_version_hash = compute_hash(payload_to_hash)
    
    final_dataset = {
        "metadata": {
            "version_hash": dataset_version_hash,
            "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT"),
            "description": "SSR 2.0 Immutable Golden Benchmark Corpus",
            "case_count": len(cases)
        },
        "gold_standards_reference": gs_sheets,
        "cases": cases
    }
    
    os.makedirs(os.path.dirname(os.path.abspath(GOLDEN_DATASET_PATH)), exist_ok=True)
    with open(GOLDEN_DATASET_PATH, 'w', encoding='utf-8') as f:
        json.dump(final_dataset, f, indent=4)
        
    print(f"[BUILDER] Success! Dataset Version {dataset_version_hash} saved with {len(cases)} cases.")
    return dataset_version_hash

if __name__ == "__main__":
    build_dataset()