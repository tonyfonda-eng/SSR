import os
import json

def seed():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    schema_path = os.path.join(root, 'src/knowledge/registry/object_schemas.json')
    
    with open(schema_path, 'r') as f: schemas = json.load(f)
    if not any(s["schema_id"] == "SCHEMA.DOC.SEC_FILING" for s in schemas):
        schemas.append({
            "schema_id": "SCHEMA.DOC.SEC_FILING",
            "version": "1.0",
            "name": "SEC Regulatory Filing",
            "layer": "Document",
            "fields": [
                { "name": "ticker", "datatype": "string", "required": True },
                { "name": "form_type", "datatype": "string", "required": True },
                { "name": "accession_number", "datatype": "string", "required": True },
                { "name": "filing_date", "datatype": "string", "required": True },
                { "name": "document_url", "datatype": "string", "required": True }
            ],
            "validation_rules": [],
            "maturity": "Institutional"
        })
        with open(schema_path, 'w') as f: json.dump(schemas, f, indent=2)
        print("[✓] SEC Filing Schema Injected.")

if __name__ == "__main__":
    seed()
