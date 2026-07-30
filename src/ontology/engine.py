import os
import json
from typing import Dict, Optional, List

class SSROntologyEngine:
    def __init__(self):
        self.nodes: Dict[str, dict] = {}
        self._load_graph()

    def _load_graph(self):
        """Sweeps the validated data directories and loads the graph into memory."""
        data_dir = os.path.join(os.path.dirname(__file__), 'data')
        if not os.path.exists(data_dir):
            return

        for root, _, files in os.walk(data_dir):
            for file in files:
                if file.endswith('.json'):
                    path = os.path.join(root, file)
                    try:
                        with open(path, 'r') as f:
                            items = json.load(f)
                            for item in items:
                                oid = item.get("ontology_id")
                                if oid:
                                    self.nodes[oid.upper()] = item
                    except Exception as e:
                        print(f"[Ontology Engine] Error loading {file}: {e}")

    def get_node(self, ontology_id: str) -> Optional[dict]:
        """O(1) direct lookup for a specific node."""
        return self.nodes.get(ontology_id.upper())

    def get_all_nodes(self) -> Dict[str, dict]:
        """Returns the complete active graph."""
        return self.nodes

    def get_nodes_by_instrument(self, instrument: str) -> List[dict]:
        """Filters the graph to return only nodes eligible for a specific asset class."""
        target = instrument.upper()
        return [
            node for node in self.nodes.values() 
            if target in [i.upper() for i in node.get("eligible_instruments", [])]
        ]

# Global Singleton Instance for Runtime Execution
Ontology = SSROntologyEngine()
