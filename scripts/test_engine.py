import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.ontology.engine import Ontology

def main():
    print("==================================================")
    print(" SSR IN-MEMORY ONTOLOGY ENGINE TEST ")
    print("==================================================")
    
    total_nodes = len(Ontology.get_all_nodes())
    print(f"Total Active Nodes in Memory: {total_nodes}")
    
    print("\n--- Testing Direct Lookup (O(1)) ---")
    target_id = "CC-001-A4"
    node = Ontology.get_node(target_id)
    if node:
        print(f"FOUND: {node['ontology_id']} | {node['canonical_name']}")
        print(f"Playbook Pointer: {node['playbook_template_id']}")
    else:
        print(f"FAILED: Could not locate {target_id}")

    print("\n--- Testing Instrument Filtering ---")
    # Finding all actions that affect Exchange Traded Funds
    etf_events = Ontology.get_nodes_by_instrument("ETF")
    print(f"Found {len(etf_events)} event(s) eligible for ETF instruments:")
    for event in etf_events:
        print(f"  -> {event['ontology_id']}: {event['canonical_name']}")
        
    print("==================================================")

if __name__ == "__main__":
    main()
