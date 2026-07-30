import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.engine.planner import ExecutionPlanner

def main():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    planner = ExecutionPlanner(root)
    
    print("==================================================")
    print(" SSR EXECUTION PLANNER COMPILATION TEST")
    print("==================================================")
    
    try:
        # Compile a Fast Triage Plan for a hypothetical Cash Merger
        plan = planner.compile_plan(
            event_id="EVT_DSGR_MERGER_001",
            playbook_id="PLAYBOOK_CASH_MERGER",
            policy_id="POLICY_FAST_TRIAGE"
        )
        print(json.dumps(plan, indent=2))
        
        print("\n[SUCCESS] DAG successfully resolved dependencies.")
        print(f"Topological Root: {plan['topological_sequence'][0]} (Has zero dependencies)")
    except Exception as e:
        print(f"FAILED: {e}")
        
    print("==================================================")

if __name__ == "__main__":
    main()
