import os
import json

def seed_registries():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    schema_path = os.path.join(root, 'src/knowledge/registry/object_schemas.json')
    obj_path = os.path.join(root, 'src/knowledge/registry/canonical_objects.json')

    # 1. Inject SCHEMA.OPT.CONTRACT
    with open(schema_path, 'r') as f: schemas = json.load(f)
    if not any(s["schema_id"] == "SCHEMA.OPT.CONTRACT" for s in schemas):
        schemas.append({
            "schema_id": "SCHEMA.OPT.CONTRACT",
            "version": "1.0",
            "name": "Standardized Options Contract",
            "layer": "Financial",
            "fields": [
                { "name": "underlying_ticker", "datatype": "string", "required": True },
                { "name": "occ_symbol", "datatype": "string", "required": False },
                { "name": "strike", "datatype": "float", "required": True },
                { "name": "expiry", "datatype": "string", "required": True },
                { "name": "option_type", "datatype": "string", "required": True },
                { "name": "multiplier", "datatype": "float", "required": True },
                { "name": "is_adjusted", "datatype": "boolean", "required": True }
            ],
            "validation_rules": ["strike >= 0.0"],
            "maturity": "Verified"
        })
        with open(schema_path, 'w') as f: json.dump(schemas, f, indent=2)

    # 2. Inject OBJ.OPT.OPTION_CONTRACT
    with open(obj_path, 'r') as f: objects = json.load(f)
    if not any(o["object_id"] == "OBJ.OPT.OPTION_CONTRACT" for o in objects):
        objects.append({
            "object_id": "OBJ.OPT.OPTION_CONTRACT",
            "name": "OCC Option Contract Definition",
            "definition": "Metadata for a specific tradeable option contract.",
            "semantic_type": "Fact",
            "uses_schema_id": "SCHEMA.OPT.CONTRACT",
            "source_module": "UNI.SECURITIES",
            "maturity": "Verified"
        })
        with open(obj_path, 'w') as f: json.dump(objects, f, indent=2)
        print("[✓] Option Contract Schemas Successfully Injected.")

if __name__ == "__main__":
    seed_registries()
