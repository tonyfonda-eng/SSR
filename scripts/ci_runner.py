import os
import json
import time
import sys
from collections import defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.knowledge.schemas.governance import CalculationDefinition
from src.engine.calculations import CALC_IMPLEMENTATION_MAP

def check_dag_cycles(calcs: dict) -> bool:
    """Kahn's algorithm to ensure no infinite calculation loops exist."""
    in_degree = {cid: 0 for cid in calcs}
    adj = {cid: [] for cid in calcs}
    
    for cid, cdata in calcs.items():
        for req in cdata.required_inputs:
            if req.startswith("CALC."):
                if req not in calcs:
                    raise ValueError(f"Missing dependency: {cid} depends on {req}")
                adj[req].append(cid)
                in_degree[cid] += 1
                
    queue = [n for n in in_degree if in_degree[n] == 0]
    visited = 0
    while queue:
        node = queue.pop(0)
        visited += 1
        for neighbor in adj[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
                
    return visited == len(calcs)

def main():
    print("==================================================")
    print("  SSR REGISTRY VALIDATION ENGINE (CI RUNNER) ")
    print("==================================================")
    
    calc_dir = os.path.join(os.path.dirname(__file__), '../src/knowledge/registry/calculations')
    calc_objects = {}
    
    # 1 & 2: JSON Syntax & Schema Validation
    for file in os.listdir(calc_dir):
        if file.endswith(".json"):
            with open(os.path.join(calc_dir, file), 'r') as f:
                data = json.load(f)
                calc_obj = CalculationDefinition(**data)
                calc_objects[calc_obj.calc_id] = calc_obj
                
    print(f"[✓] Loaded and validated {len(calc_objects)} calculation schemas.")
    
    # 3: Graph Integrity (DAG)
    if not check_dag_cycles(calc_objects):
        print("[X] ERROR: Cycle detected in Calculation DAG.")
        sys.exit(1)
    print("[✓] Calculation DAG is clean. No cycles detected.")
    
    # 4: Test Vectors & Benchmarking
    passed = 0
    failed = 0
    coverage = defaultdict(int)
    
    print("\n--- Executing Test Vectors ---")
    for cid, calc in calc_objects.items():
        func = CALC_IMPLEMENTATION_MAP.get(calc.implementation.function_name)
        if not func:
            print(f"[X] Missing python implementation: {calc.implementation.function_name}")
            sys.exit(1)
            
        for test in calc.test_vectors:
            t0 = time.perf_counter()
            result = func(test.input_values)
            t1 = time.perf_counter()
            
            diff = abs(result - test.expected_output)
            if diff <= test.absolute_tolerance:
                passed += 1
                coverage[calc.family] += 1
                print(f" [PASS] {cid} | Runtime: {(t1-t0)*1000:.4f} ms")
            else:
                failed += 1
                print(f" [FAIL] {cid} | Expected: {test.expected_output}, Got: {result}")
                
    print("\n==================================================")
    print(f" Executed Tests : {passed + failed}")
    print(f" Passed         : {passed}")
    print(f" Failed         : {failed}")
    print("--------------------------------------------------")
    print(" Coverage by Family:")
    for family, count in coverage.items():
        print(f"  {family.ljust(15)} : {count} passing vectors")
    print("==================================================")
    
    if failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
