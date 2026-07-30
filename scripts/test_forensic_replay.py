import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.engine.orchestrator import ExecutionOrchestrator
from src.engine.runtime import ExecutionContext

def run_replay_test():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    orchestrator = ExecutionOrchestrator(root)
    
    active_calcs = [
        "CALC.OBJ.OPT.INTRINSIC_VALUE",
        "CALC.OBJ.OPT.EXTRINSIC_VALUE",
        "CALC.ANALYTICS.OPT.ARB_BREAK_EVEN",
        "CALC.ANALYTICS.OPT.ASSIGNMENT_RISK"
    ]
    
    print("=== STARTING FORENSIC REPLAY INTEGRATION TEST ===")
    
    # --------------------------------------------------
    # RUN 1: INITIAL STATE GENERATION
    # --------------------------------------------------
    print("\n[*] Execution Run 1: Hydrating data variables...")
    ctx1 = orchestrator.bootstrap_context("EVT.2026.REPLAY_PROOF", active_calcs)
    
    # Simulating data arriving over the wire via the EventBus
    ctx1.bus.publish("OBJ.OPT.OPTION_CONTRACT", {"option_type": "call", "strike": 40.0})
    ctx1.bus.publish("OBJ.MKT.PRICE_SNAPSHOT", {"price": 46.50})
    ctx1.bus.publish("OBJ.MKT.PREMIUM_SNAPSHOT", {"price": 8.00})
    
    # Capture the generated calculation results
    hash_run1 = {k: v.input_hash for k, v in ctx1.calculation_results.items()}
    val_run1 = {k: v.result_value for k, v in ctx1.calculation_results.items()}
    
    snap_file = os.path.join(root, "snapshot_run1.json")
    ctx1.snapshot(snap_file)
    
    # --------------------------------------------------
    # RUN 2: FORENSIC HYDRATION & REPLAY
    # --------------------------------------------------
    print("\n[*] Execution Run 2: Rehydrating from Snapshot file...")
    ctx2 = ExecutionContext.load(snap_file, orchestrator.registry, ctx1.bus.impl_map)
    ctx2.bus.configure_active_calculations(active_calcs)
    
    # Wipe calculation results out of the context to prove they can be cleanly re-derived
    ctx2.calculation_results.clear()
    
    print("[*] Re-triggering event propagation loop...")
    # Re-inject the initial entries to spark the reactive bus back into motion
    ctx2.bus.publish("OBJ.OPT.OPTION_CONTRACT", ctx2.market_snapshots["OBJ.OPT.OPTION_CONTRACT"])
    ctx2.bus.publish("OBJ.MKT.PRICE_SNAPSHOT", ctx2.market_snapshots["OBJ.MKT.PRICE_SNAPSHOT"])
    ctx2.bus.publish("OBJ.MKT.PREMIUM_SNAPSHOT", ctx2.market_snapshots["OBJ.MKT.PREMIUM_SNAPSHOT"])
    
    hash_run2 = {k: v.input_hash for k, v in ctx2.calculation_results.items()}
    val_run2 = {k: v.result_value for k, v in ctx2.calculation_results.items()}
    
    # --------------------------------------------------
    # INVARIANT VALIDATION MATRICES
    # --------------------------------------------------
    print("\n=== VERIFYING DETERMINISTIC HASH INVARIANTS ===")
    all_passed = True
    
    for obj_id in hash_run1:
        h1 = hash_run1[obj_id]
        h2 = hash_run2.get(obj_id)
        v1 = val_run1[obj_id]
        v2 = val_run2.get(obj_id)
        
        print(f"\n[Node: {obj_id}]")
        print(f"  - Run 1: Val = {v1} | Hash = {h1[:12]}")
        print(f"  - Run 2: Val = {v2} | Hash = {h2[:12] if h2 else 'NONE'}")
        
        if h1 == h2 and v1 == v2:
            print("  Status: MATCHED 🟢")
        else:
            print("  Status: FAILURE 🔴")
            all_passed = False
            
    print("\n--------------------------------------------------")
    if all_passed:
        print("RESULT: PROVEN 🟢 | The Replay Guarantee is verified invariant.")
    else:
        print("RESULT: FAILED 🔴 | State non-determinism detected.")
    print("--------------------------------------------------\n")

if __name__ == "__main__":
    run_replay_test()
