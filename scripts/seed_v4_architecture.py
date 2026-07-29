import os
import json

def seed():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    schema_path = os.path.join(root, 'src/knowledge/registry/object_schemas.json')
    
    with open(schema_path, 'r') as f: schemas = json.load(f)
    
    # Clean out old drafts
    schemas = [s for s in schemas if s["schema_id"] not in ["SCHEMA.OPT.CONTRACT", "SCHEMA.MKT.SNAPSHOT"]]
    
    # 1. Inject Expanded Option Contract
    schemas.append({
        "schema_id": "SCHEMA.OPT.CONTRACT",
        "version": "2.0",
        "name": "Institutional Option Contract",
        "fields": [
            { "name": "underlying_ticker", "datatype": "string", "required": True },
            { "name": "occ_symbol", "datatype": "string", "required": True },
            { "name": "strike", "datatype": "float", "required": True },
            { "name": "expiration", "datatype": "datetime", "required": True },
            { "name": "option_type", "datatype": "string", "required": True },
            { "name": "exercise_style", "datatype": "string", "required": True },
            { "name": "multiplier", "datatype": "float", "required": True },
            { "name": "deliverable", "datatype": "string", "required": True },
            { "name": "settlement_type", "datatype": "string", "required": True },
            { "name": "listing_exchange", "datatype": "string", "required": True },
            { "name": "is_adjusted", "datatype": "boolean", "required": True },
            { "name": "occ_memo_id", "datatype": "string", "required": False },
            { "name": "contract_size", "datatype": "int", "required": True },
            { "name": "currency", "datatype": "string", "required": True }
        ],
        "validation_rules": ["strike >= 0.0"],
        "maturity": "Institutional"
    })
    
    # 2. Inject Market Snapshot
    schemas.append({
        "schema_id": "SCHEMA.MKT.SNAPSHOT",
        "version": "1.0",
        "name": "Market Price Snapshot",
        "fields": [
            { "name": "timestamp", "datatype": "datetime", "required": True },
            { "name": "price", "datatype": "float", "required": True },
            { "name": "bid", "datatype": "float", "required": False },
            { "name": "ask", "datatype": "float", "required": False },
            { "name": "volume", "datatype": "int", "required": False },
            { "name": "exchange", "datatype": "string", "required": False }
        ],
        "validation_rules": ["price >= 0.0"],
        "maturity": "Institutional"
    })

    with open(schema_path, 'w') as f: json.dump(schemas, f, indent=2)
    print("[✓] V4 Schema Namespaces and Provenance Objects Successfully Seeded.")

if __name__ == "__main__":
    seed()
