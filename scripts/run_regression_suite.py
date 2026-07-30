import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.engine.orchestrator import ExecutionOrchestrator

def run_regression():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    orchestrator = ExecutionOrchestrator(root)
    
    manifest_path = os.path.join(root, "fixtures/fixture_manifest.json")
    if not os.path.exists(manifest_path):
        print("[!] Error: Fixture manifest not found.")
        sys.exit(1)
        
    with open(manifest_path, 'r') as f:
        manifest = json.load(f)
        
    active_calcs = [
        "CALC.OBJ.OPT.INTRINSIC_VALUE",
        "CALC.OBJ.OPT.EXTRINSIC_VALUE",
        "CALC.MNA.OPT.MERGER_PAYOFF"
    ]
    
    print(f"\n=== RUNNING REGRESSION SUITE (Corpus v{manifest['corpus_version']}) ===")
    passed_count = 0
    total_count = len(manifest["fixtures"])
    
    for item in manifest["fixtures"]:
        fixture_id = item["fixture_id"]
        fixture_dir = os.path.join(root, item["path"])
        print(f"\n[*] Evaluating Fixture: {fixture_id}...")
        
        input_path = os.path.join(fixture_dir, "input_state.json")
        expected_path = os.path.join(fixture_dir, "expected_snapshot.json")
        
        if not os.path.exists(input_path) or not os.path.exists(expected_path):
            print(f"  [!] Missing physical files for fixture {fixture_id}. Skipping.")
            continue
            
        with open(input_path, 'r') as f: inputs = json.load(f)
        with open(expected_path, 'r') as f: expected = json.load(f)
        
        ctx = orchestrator.bootstrap_context(inputs["event_id"], active_calcs)
        
        # Publish base static records first
        ctx.bus.publish("OBJ.PORT.POSITION_RECORD", inputs["position_record"])
        ctx.bus.publish("OBJ.OPT.OPTION_CONTRACT", inputs["option_contract"])
        ctx.bus.publish("OBJ.MKT.PRICE_SNAPSHOT", inputs["market_price"])
        
        # Publish optional secondary considerations BEFORE the primary cash trigger
        if "cvr_consideration" in inputs:
            ctx.bus.publish("OBJ.FIN.CVR_CONSIDERATION", inputs["cvr_consideration"])
            
        # Publish primary trigger last so all context is fully loaded in state
        ctx.bus.publish("OBJ.FIN.CASH_CONSIDERATION", inputs["cash_consideration"])
            
        fixture_passed = True
        for obj_id, expected_val in expected["expected_values"].items():
            res_obj = ctx.calculation_results.get(obj_id)
            if not res_obj:
                print(f"  [X] Node {obj_id} missing from execution results.")
                fixture_passed = False
                continue
                
            actual_val = res_obj.result_value
            if actual_val != expected_val:
                print(f"  [X] Mismatch on {obj_id}: Expected {expected_val}, got {actual_val}")
                fixture_passed = False
            else:
                print(f"  [✓] Node {obj_id} matches expected value ({actual_val})")
                
        if fixture_passed:
            print(f"  RESULT: PASS 🟢")
            passed_count += 1
        else:
            print(f"  RESULT: FAIL 🔴")
            
    print("\n==================================================")
    print(f"REGRESSION COMPLETE: {passed_count}/{total_count} Fixtures Passed.")
    if passed_count == total_count:
        print("REPLAY FIDELITY KPI: 100% 🟢")
        sys.exit(0)
    else:
        print("REPLAY FIDELITY KPI: FAILED 🔴")
        sys.exit(1)

if __name__ == "__main__":
    run_regression()
