import os
import json
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from src.knowledge.schemas.epistemology import KnowledgeAssertion, AssertionRevision, GraphEdge, NodeReference

class RegistryManager:
    """The central storage engine. Loads, validates, and serves all metadata registries."""
    def __init__(self, root_dir: str):
        self.root_dir = root_dir
        self.schemas: Dict[str, dict] = {}
        self.objects: Dict[str, dict] = {}
        self.relationships: Dict[str, dict] = {}
        self.calculations: Dict[str, dict] = {}
        self.load_registries()

    def load_registries(self):
        # Load Schemas
        schema_path = os.path.join(self.root_dir, 'src/knowledge/registry/object_schemas.json')
        if os.path.exists(schema_path):
            with open(schema_path, 'r') as f:
                for s in json.load(f): self.schemas[s["schema_id"]] = s
                
        # Load Conceptual Objects
        obj_path = os.path.join(self.root_dir, 'src/knowledge/registry/canonical_objects.json')
        if os.path.exists(obj_path):
            with open(obj_path, 'r') as f:
                for o in json.load(f): self.objects[o["object_id"]] = o

        # Load Relationships
        rel_path = os.path.join(self.root_dir, 'src/knowledge/registry/relationships.json')
        if os.path.exists(rel_path):
            with open(rel_path, 'r') as f:
                for r in json.load(f): self.relationships[r["relationship_id"]] = r
                
        # Load Calculations (Directory Scan)
        calc_dir = os.path.join(self.root_dir, 'src/knowledge/registry/calculations')
        if os.path.exists(calc_dir):
            for file in os.listdir(calc_dir):
                if file.endswith(".json"):
                    with open(os.path.join(calc_dir, file), 'r') as f:
                        c = json.load(f)
                        self.calculations[c["calc_id"]] = c

    def get_schema(self, schema_id: str) -> Optional[dict]: return self.schemas.get(schema_id)
    def get_object(self, object_id: str) -> Optional[dict]: return self.objects.get(object_id)
    def get_relationship(self, rel_id: str) -> Optional[dict]: return self.relationships.get(rel_id)
    def get_calculation(self, calc_id: str) -> Optional[dict]: return self.calculations.get(calc_id)


class SchemaValidator:
    """Gatekeeper. Validates CandidateAssertions against their target SCHEMA properties."""
    def __init__(self, registry: RegistryManager):
        self.registry = registry

    def validate_candidate(self, candidate: dict) -> tuple[bool, List[str]]:
        errors = []
        schema_id = candidate.get("schema_id")
        payload = candidate.get("value_payload", {})
        
        schema = self.registry.get_schema(schema_id)
        if not schema:
            return False, [f"Schema definition '{schema_id}' not found in registry."]

        for field in schema.get("fields", []):
            f_name = field["name"]
            f_type = field["datatype"]
            
            if field["required"] and f_name not in payload:
                errors.append(f"Required field '{f_name}' is missing from payload.")
                continue
                
            if f_name in payload:
                val = payload[f_name]
                if f_type == "float" and not isinstance(val, (int, float)):
                    errors.append(f"Field '{f_name}' must be a float. Got {type(val).__name__}.")
                elif f_type == "string" and not isinstance(val, str):
                    errors.append(f"Field '{f_name}' must be a string. Got {type(val).__name__}.")
                elif f_type == "boolean" and not isinstance(val, bool):
                    errors.append(f"Field '{f_name}' must be a boolean. Got {type(val).__name__}.")

        for rule in schema.get("validation_rules", []):
            if "matches" in rule:
                parts = rule.split(" matches ")
                f_target = parts[0]
                pattern = parts[1]
                if f_target in payload and not re.match(pattern, str(payload[f_target])):
                    errors.append(f"Field '{f_target}' failed validation rule: must match {pattern}.")
            elif ">= 0.0" in rule:
                f_target = rule.split(" ")[0]
                if f_target in payload and payload[f_target] < 0.0:
                    errors.append(f"Field '{f_target}' failed boundary rule: must be >= 0.0.")

        return len(errors) == 0, errors


class GraphLinker:
    """Purely deterministic engine. Dynamically wires graph edges across validated facts."""
    def __init__(self, registry: RegistryManager):
        self.registry = registry

    def derive_edges(self, assertions: List[KnowledgeAssertion]) -> List[GraphEdge]:
        edges = []
        target_entity_node_id = None
        cash_assertion_id = None
        event_id = None

        for ast in assertions:
            event_id = ast.event_id
            if ast.object_id == "OBJ.CORP.TARGET_ENTITY":
                target_entity_node_id = ast.assertion_id
            elif ast.object_id == "OBJ.FIN.CASH_CONSIDERATION":
                cash_assertion_id = ast.assertion_id

        if cash_assertion_id and target_entity_node_id:
            edges.append(GraphEdge(
                edge_id=f"EDG.LINK.{cash_assertion_id[:8].upper()}",
                event_id=event_id,
                relationship_id="REL.APPLIES_TO",
                source=NodeReference(node_class="Fact", node_id=cash_assertion_id),
                target=NodeReference(node_class="Fact", node_id=target_entity_node_id),
                justified_by_assertions=[cash_assertion_id]
            ))
            
        return edges
