"""
SSR 2.0: Deterministic Replay Engine (Phase 3)
Re-evaluates a specific historical decision against its exact frozen Configuration Manifest
and Market Data snapshot. Intercepts external API and LLM calls to ensure zero state drift.
"""

import argparse
import sqlite3
import json
import sys
from unittest.mock import patch

from src.database import RESEARCH_DB_PATH
import monitor

def run_replay(decision_id: str) -> bool:
    print(f"\n--- SSR 2.0 DETERMINISTIC REPLAY ENGINE ---")
    print(f"Target Decision : {decision_id}")
    
    conn = sqlite3.connect(RESEARCH_DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # 1. Load Original Ledger State
    cur.execute("SELECT * FROM evaluation_ledger WHERE decision_id=?", (decision_id,))
    ledger = cur.fetchone()
    if not ledger:
        print(f"[ERROR] Decision ID {decision_id} not found in {RESEARCH_DB_PATH}")
        conn.close()
        return False
        
    event_id = ledger["event_id"]
    manifest_hash = ledger["manifest_hash"]
    original_outcome = ledger["detection_outcome"]
    original_stage = ledger["terminal_stage"]
    market_data_str = ledger["market_data_snapshot"]
    
    # 2. Load Raw Immutable Payload
    cur.execute("SELECT raw_payload_blob FROM event_registry WHERE event_id=?", (event_id,))
    event = cur.fetchone()
    raw_text = event["raw_payload_blob"].decode('utf-8') if event else ""
    
    # 3. Load Frozen Configuration Snapshot
    cur.execute("SELECT config_json FROM config_snapshots WHERE hash=?", (manifest_hash,))
    config_row = cur.fetchone()
    if not config_row:
        print(f"[ERROR] Missing config snapshot for hash {manifest_hash}")
        conn.close()
        return False
        
    config = json.loads(config_row["config_json"])
    
    # 4. Load Original AI Inference Data (to stub LLM calls)
    cur.execute("SELECT * FROM ai_core_inference WHERE decision_id=?", (decision_id,))
    ai_row = cur.fetchone()
    orig_ticker = "UNKNOWN"
    orig_strategy = "Unknown"
    
    if ai_row and ai_row["parsed_structural_properties"]:
        try:
            ai_props = json.loads(ai_row["parsed_structural_properties"])
            orig_ticker = ai_props.get("ticker", "UNKNOWN")
            orig_strategy = ai_props.get("strategy", "Unknown")
        except Exception:
            pass
            
    conn.close()
    
    # 5. Setup Pinned Financials Cache (Bypasses yfinance)
    financials_cache = {}
    if market_data_str:
        try:
            md = json.loads(market_data_str)
            financials_cache[orig_ticker] = {
                "info": {
                    "marketCap": md.get("market_cap"),
                    "currentPrice": md.get("current_price"),
                    "regularMarketPrice": md.get("current_price"),
                    "totalCash": md.get("total_cash"),
                    "totalDebt": md.get("total_debt"),
                    "previousClose": md.get("current_price")
                },
                "options_available": md.get("options_available", False)
            }
        except Exception:
            pass

    # 6. Parse text payload back into constituent parts
    parts = raw_text.split('\n\n', 1)
    title = parts[0] if len(parts) > 0 else ""
    body = parts[1] if len(parts) > 1 else ""

    primary = {
        "source_name": "REPLAY_ENGINE",
        "url": "http://replay.local",
        "title": title,
        "body": body,
        "triage_all": False,
        "document_type": "Unknown",
        "article_id": decision_id
    }

    capsule = monitor.EvidenceCapsule(event_id, decision_id, manifest_hash, raw_text)
    issuer_memory = monitor.IssuerMemory() # Empty mock
    
    print(f"Config Hash     : {manifest_hash}")
    print(f"Original Outcome: {original_outcome} (Stage: {original_stage})")
    print("Re-evaluating pipeline logic locally...")

    # 7. Isolate the environment and execute
    # We patch AI calls to ensure fast, deterministic tests without LLM drift/costs.
    # We patch DB/Email outputs to prevent spam and ledger corruption.
    with patch('monitor.commit_decision_capsule') as mock_commit, \
         patch('monitor.send_alert') as mock_alert, \
         patch('monitor.append_to_research_queue') as mock_queue, \
         patch('monitor.log_research') as mock_log, \
         patch('monitor.save_reminder') as mock_reminder, \
         patch('monitor.create_event_if_new', return_value=(event_id, True)), \
         patch('monitor.extract_target_ticker', return_value=orig_ticker), \
         patch('monitor.classify_event', return_value=orig_strategy), \
         patch('monitor.extract_halt_date', return_value=""), \
         patch('monitor.execute_playbook', return_value="[REPLAY] Historical Memo Generated."):
         
         monitor.evaluate_capsule(
             capsule=capsule,
             primary=primary,
             rules=config.get("rules", []),
             playbook_map={p['Playbook']: p.get('Questions/Research Steps', '') for p in config.get("playbooks", [])},
             global_exclusions=config.get("global_exclusions", []),
             gold_standards=config.get("gold_standards", {}),
             issuer_memory=issuer_memory,
             document_type_scores=config.get("document_type_scores", []),
             ontology_stats={"total": 0, "extracted": 0, "missed": 0},
             source_reliability_scores=config.get("source_reliability_scores", {}),
             research_queue_rows=[],
             financials_cache=financials_cache
         )
         
    new_outcome = capsule.outcome
    new_stage = capsule.terminal_stage
    
    print(f"Replay Outcome  : {new_outcome} (Stage: {new_stage})")
    
    if new_outcome == original_outcome and new_stage == original_stage:
        print("\n[✅ PASS] Deterministic Replay matched historical decision exactly.")
        return True
    else:
        print("\n[❌ FAIL] Replay diverged from historical record!")
        print(f"   Expected: {original_outcome} @ {original_stage}")
        print(f"   Got     : {new_outcome} @ {new_stage}")
        print("\n   Note: If you intentionally modified src/rules_engine.py or src/ontology/engine.py,")
        print("   this divergence is expected. Document the logic shift in your PR.")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SSR 2.0 Deterministic Replay Engine")
    parser.add_argument("--decision-id", required=True, help="The Decision ID (DSC-...) to replay")
    args = parser.parse_args()
    
    success = run_replay(args.decision_id)
    sys.exit(0 if success else 1)