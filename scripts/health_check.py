import sys
import os
import json
from typing import Set

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.engine.core import RegistryManager
from src.engine.calculations import CALC_IMPLEMENTATION_MAP

def check_registry_integrity(root: str):
    print("=== V1.0.0 System Health Check ===")
    registry = RegistryManager(root)
    
    # 1. Check Implementations
    print("\n[*] Validating Calculation Implementations...")
    missing_impl = []
    for calc_id, calc_def in registry.calculations.items():
        func_name = calc_def.get("implementation", {}).get("function")
        if func_name not in CALC_IMPLEMENTATION_MAP:
            missing_impl.append(f"{calc_id} -> {func_name}")
            
    if missing_impl:
        print("[!] ERROR: Missing Python implementations for:")
        for m in missing_impl: print(f"    - {m}")
    else:
        print("[✓] All calculations mapped to Python implementations.")

    # 2. Check DAG Acyclicity
    print("\n[*] Validating DAG Acyclicity...")
    edges = {calc_id: calc_def.get("required_inputs", []) for calc_id, calc_def in registry.calculations.items()}
    visited = set()
    path = set()
    has_cycle = False

    def visit(node: str):
        nonlocal has_cycle
        if node in path:
            has_cycle = True
            print(f"[!] CYCLE DETECTED AT: {node}")
            return
        if node in visited or node not in edges:
            return
            
        path.add(node)
        for req in edges[node]:
            # Simple check to see if a requirement is produced by another calc
            producer = next((cid for cid, c in registry.calculations.items() if c.get("produces") == req), None)
            if producer:
                visit(producer)
        path.remove(node)
        visited.add(node)

    for calc in edges: visit(calc)
    
    if not has_cycle:
        print("[✓] Math DAG is strictly acyclic.")

    print("\n=== Health Check Complete ===")

if __name__ == "__main__":
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    check_registry_integrity(root)
