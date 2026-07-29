import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.engine.core import RegistryManager, SchemaValidator, GraphLinker
from src.knowledge.schemas.epistemology import KnowledgeAssertion

def main():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    
    # 1. Initialize Registry Manager
    registry = RegistryManager(root)
    validator = SchemaValidator(registry)
    linker = GraphLinker(registry)
    
    print("==================================================")
    # Mocking extraction data inputs - Fixed to use Python capitalization rules
    mock_candidates = [
      {
        "candidate_id": "CND.001",
        "event_id": "EVT.DSGR.2026",
        "schema_id": "SCHEMA.FIN.CURRENCY_AMOUNT",
        "object_id": "OBJ.FIN.CASH_CONSIDERATION",
        "value_payload": { "amount": 50.00, "currency_code": "USD", "gross_net": "Gross", "per_share": True },
        "basis_observations": ["OBS.001"],
        "confidence_method": "TablePriority",
        "extractor_profile_id": "EXEC.UNI.CONSIDERATION.v3"
      },
      {
        "candidate_id": "CND.002",
        "event_id": "EVT.DSGR.2026",
        "schema_id": "SCHEMA.FIN.CURRENCY_AMOUNT",
        "object_id": "OBJ.FIN.CASH_CONSIDERATION",
        "value_payload": { "amount": -10.00, "currency_code": "INVALID_C_CODE", "gross_net": "Gross", "per_share": True },
        "basis_observations": ["OBS.002"],
        "confidence_method": "TablePriority",
        "extractor_profile_id": "EXEC.UNI.CONSIDERATION.v3"
      }
    ]

    print(" STEP 1: PROCESSING EXTRACTIONS THROUGH VALIDATOR")
    print("--------------------------------------------------")
    
    promoted_assertions = []
    for index, cnd in enumerate(mock_candidates, 1):
        is_valid, errors = validator.validate_candidate(cnd)
        if is_valid:
            print(f"[✓] Candidate {index} Passed Validation. Promoting to Knowledge Graph.")
            ast = KnowledgeAssertion(
                assertion_id=f"AST.FACT.{cnd['candidate_id'].split('.')[1]}",
                event_id=cnd["event_id"],
                schema_id=cnd["schema_id"],
                object_id=cnd["object_id"]
            )
            promoted_assertions.append(ast)
        else:
            print(f"[X] Candidate {index} REJECTED by Gatekeeper Engine:")
            for err in errors:
                print(f"     ↳ Error: {err}")

    # Injecting Target Entity Node to evaluate Linking Engine
    promoted_assertions.append(KnowledgeAssertion(
        assertion_id="AST.FACT.003", event_id="EVT.DSGR.2026",
        schema_id="SCHEMA.CORP.LEGAL_ENTITY", object_id="OBJ.CORP.TARGET_ENTITY"
    ))

    print("\n STEP 2: PROCESSING PROMOTED ASSETS THROUGH LINKER")
    print("--------------------------------------------------")
    derived_edges = linker.derive_edges(promoted_assertions)
    
    for edge in derived_edges:
        print(f"[✓] Graph Relationship Wired automatically:")
        print(f"     Source Node: {edge.source.node_id} ({edge.source.node_class})")
        print(f"     Edge link  : --[{edge.relationship_id}]-->")
        print(f"     Target Node: {edge.target.node_id} ({edge.target.node_class})")
    print("==================================================")

if __name__ == "__main__":
    main()
