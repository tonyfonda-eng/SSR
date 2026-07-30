import os
import json
import sys

# Controlled Target Vocabularies
VALID_JURISDICTIONS = {"GLOBAL", "US", "UK", "CA", "AU", "HK", "JP", "EU"}
VALID_INSTRUMENTS = {"COMMON STOCK", "PREFERRED STOCK", "ADR", "ETF", "CEF", "SPAC", "BOND", "TRUST UNITS"}
VALID_STATUSES = {"Active", "Deprecated"}
VALID_TIMELINES = {"Days", "Weeks", "Months", "Years", "Variable"}
VALID_RECIPIENTS = {"Shareholders", "Bondholders", "Unitholders", "Creditors", "SPAC Holders"}

# The official Institutional Root Branches
VALID_ROOTS = {
    "CC-ROOT", "DIS-ROOT", "CAP-ROOT", "SEC-ROOT", "LFC-ROOT", 
    "COR-ROOT", "FND-ROOT", "DST-ROOT", "DBT-ROOT", "GOV-ROOT", "SPT-ROOT", "LIQ-ROOT"
}

class OntologyValidator:
    def __init__(self, target_dir: str):
        self.target_dir = target_dir
        self.nodes = {}
        self.errors = []
        self.all_aliases = set()

    def run_validation_suite(self) -> bool:
        self._load_and_parse_files()
        if self.errors:
            return False

        self._validate_structural_integrity()
        self._validate_semantic_constraints()
        
        return len(self.errors) == 0

    def _load_and_parse_files(self):
        for root, _, files in os.walk(self.target_dir):
            for file in files:
                if file.endswith('.json'):
                    path = os.path.join(root, file)
                    try:
                        with open(path, 'r') as f:
                            items = json.load(f)
                            for item in items:
                                oid = item.get("ontology_id")
                                if not oid:
                                    self.errors.append(f"[{file}] Missing absolute 'ontology_id'")
                                    continue
                                if oid in self.nodes:
                                    self.errors.append(f"Duplicate Ontology ID discovered: {oid}")
                                self.nodes[oid] = item
                    except Exception as e:
                        self.errors.append(f"JSON Parse Failure in {file}: {e}")

    def _validate_structural_integrity(self):
        for oid, node in self.nodes.items():
            parent_id = node.get("parent_id")
            
            # Allow official root nodes to establish baseline branches cleanly
            if parent_id not in VALID_ROOTS:
                if parent_id not in self.nodes:
                    self.errors.append(f"[{oid}] Structural Error: Parent ID '{parent_id}' does not exist (Orphan Node).")
            
            if node.get("status") not in VALID_STATUSES:
                self.errors.append(f"[{oid}] Invalid Status value: {node.get('status')}")

            # Cycle Check
            current_parent = parent_id
            visited = {oid}
            while current_parent and current_parent in self.nodes:
                if current_parent in visited:
                    self.errors.append(f"[{oid}] Circular reference trace detected inside parent loop: {current_parent}")
                    break
                visited.add(current_parent)
                current_parent = self.nodes[current_parent].get("parent_id")

    def _validate_semantic_constraints(self):
        mandatory_fields = [
            "definition", "expected_cash_recipient", "typical_timeline", 
            "playbook_template_id", "alpha_profile_id", "detection_keywords"
        ]
        
        for oid, node in self.nodes.items():
            for field in mandatory_fields:
                if not node.get(field):
                    self.errors.append(f"[{oid}] Semantic Error: Missing field parameter '{field}'")

            for j in node.get("applicable_jurisdictions", []):
                if j.upper() not in VALID_JURISDICTIONS:
                    self.errors.append(f"[{oid}] Controlled Vocabulary Mismatch: Invalid Jurisdiction '{j}'")

            for i in node.get("eligible_instruments", []):
                if i.upper() not in VALID_INSTRUMENTS:
                    self.errors.append(f"[{oid}] Controlled Vocabulary Mismatch: Invalid Instrument '{i}'")

            if node.get("typical_timeline") not in VALID_TIMELINES:
                self.errors.append(f"[{oid}] Controlled Vocabulary Mismatch: Invalid Timeline '{node.get('typical_timeline')}'")

            if node.get("expected_cash_recipient") not in VALID_RECIPIENTS:
                self.errors.append(f"[{oid}] Controlled Vocabulary Mismatch: Invalid Recipient '{node.get('expected_cash_recipient')}'")

            for alias in node.get("aliases", []):
                if alias.lower() in self.all_aliases:
                    print(f"[Validator Warning] Shared alias phrase found: '{alias}' (Non-blocking).")
                self.all_aliases.add(alias.lower())

            for rel in node.get("related_ontology_nodes", []):
                if rel not in self.nodes:
                    self.errors.append(f"[{oid}] Broken Relationship: Target linked node '{rel}' does not exist.")

    def print_report(self):
        if not self.errors:
            print("\n==================================================")
            print("  ONTOLOGY VALIDATION SUCCESS: ALL NODES COMPLIANT ")
            print(f"  Parsed Nodes Count: {len(self.nodes)}")
            print("==================================================")
        else:
            print("\n==================================================")
            print(f"  ONTOLOGY VALIDATION FAILED: {len(self.errors)} STRUCTURAL ERRORS FOUND")
            print("==================================================")
            for err in self.errors:
                print(f" [X] {err}")
            print("==================================================")

if __name__ == "__main__":
    target = os.path.abspath(os.path.join(os.path.dirname(__file__), 'data'))
    validator = OntologyValidator(target)
    success = validator.run_validation_suite()
    validator.print_report()
    sys.exit(0 if success else 1)
