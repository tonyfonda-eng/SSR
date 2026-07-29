import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.engine.orchestrator import ExecutionOrchestrator
from src.engine.runtime import ExecutionContext

def main():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    orchestrator = ExecutionOrchestrator(root)
    
    active_calcs = [
        "CALC.OBJ.OPT.INTRINSIC_VALUE",
        "CALC.OBJ.OPT.EXTRINSIC_VALUE",
        "CALC.ANALYTICS.OPT.ARB_BREAK_EVEN",
        "CALC.ANALYTICS.OPT.ASSIGNMENT_RISK"
    ]
    
    print("\n==================================================")
    print("V1.0.0 Execution & Snapshot Test")
    print("==================================================")
    
    ctx = ExecutionContext("EVT.2026.FREEZE_RUN")
    
    # 1. Publish baseline objects via EventBus
    ctx.bus.publish("OBJ.OPT.OPTION_CONTRACT", {"option_type": "call", "strike": 35.0})
    ctx.bus.publish("OBJ.MKT.PRICE_SNAPSHOT", {"price": 38.50})
    ctx.bus.publish("OBJ.MKT.PREMIUM_SNAPSHOT", {"price": 4.50})
    
    # 2. Execute Deterministic Math
    orchestrator.execute_event_with_context(ctx, active_calcs)
    
    # 3. Snapshot state to disk
    snapshot_path = os.path.join(root, "snapshot_v1.json")
    ctx.snapshot(snapshot_path)
    
    print("\n[✓] Validating Snapshot Output:")
    with open(snapshot_path, 'r') as f:
        data = json.load(f)
        print(f"  - Event ID: {data['event_id']}")
        print(f"  - Objects Tracked: {len(data['available_objects'])}")
        print(f"  - Math Executions: {len(data['calculation_results'])}")
        
    print("\n==================================================")

if __name__ == "__main__":
    main()
