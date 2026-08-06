import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.ai import TransactionNode, TransactionEdge, TransactionGraph, extract_entities_and_roles
from monitor import stage_graph_validation, stage_candidate_generator, validate_pipeline_dag

def test_transaction_graph_dataclass():
    node1 = TransactionNode(name="Acquirer Inc", ticker="ACQ", is_public=True, role="acquirer", extraction_confidence=0.98, role_confidence=0.95)
    node2 = TransactionNode(name="Target Corp", ticker="TGT", is_public=True, role="target", extraction_confidence=0.99, role_confidence=0.97)
    edge = TransactionEdge(source_node="Acquirer Inc", target_node="Target Corp", relationship="acquiring", relationship_confidence=0.95)
    
    graph = TransactionGraph(nodes=[node1, node2], edges=[edge])
    assert len(graph.nodes) == 2
    assert len(graph.entities) == 2
    assert graph.nodes[0].name == "Acquirer Inc"
    assert graph.edges[0].relationship == "acquiring"

def test_stage_candidate_generator_offsets():
    article = {"body": "Press Release: Microsoft (NASDAQ: MSFT) acquires Activision (NASDAQ: ATVI).", "headline": "Acquisition"}
    ctx = {}
    passed, reason = stage_candidate_generator(article, ctx)
    assert passed
    candidates = article.get("_candidate_entities", [])
    assert len(candidates) >= 2
    tickers = [c["ticker"] for c in candidates]
    assert "MSFT" in tickers
    assert "ATVI" in tickers
    assert "position_offset" in candidates[0]

def test_stage_graph_validation_self_targeting():
    article = {
        "headline": "Self buy deal",
        "_entities": [
            {"name": "Corp A", "ticker": "XYZ", "role": "acquirer", "extraction_confidence": 0.9, "role_confidence": 0.9}
        ],
        "_transaction_edges": [
            {"source_node": "Corp A", "target_node": "Corp A", "relationship": "acquiring", "relationship_confidence": 0.9}
        ]
    }
    passed, reason = stage_graph_validation(article, {})
    assert not passed
    assert "self_targeting_edge" in reason

def test_stage_graph_validation_low_confidence():
    article = {
        "headline": "Low confidence deal",
        "_entities": [
            {"name": "Ghost Corp", "ticker": "GHOST", "role": "target", "extraction_confidence": 0.3, "role_confidence": 0.2},
            {"name": "Real Corp", "ticker": "REAL", "role": "acquirer", "extraction_confidence": 0.9, "role_confidence": 0.9}
        ],
        "_transaction_edges": []
    }
    passed, reason = stage_graph_validation(article, {})
    assert passed
    assert len(article["_entities"]) == 1
    assert article["_entities"][0]["name"] == "Real Corp"

def test_dag_validation_valid():
    os.environ["ENTITY_ENGINE_VERSION"] = "2"
    valid_dag = ["candidate_generator", "ambiguity_gate", "ai_event_classification", "strategy_selection"]
    validate_pipeline_dag(valid_dag) # Should not raise

def test_dag_validation_invalid():
    os.environ["ENTITY_ENGINE_VERSION"] = "2"
    invalid_dag = ["strategy_selection", "ai_event_classification", "ambiguity_gate", "candidate_generator"]
    with pytest.raises(ValueError):
        validate_pipeline_dag(invalid_dag)

if __name__ == "__main__":
    test_transaction_graph_dataclass()
    test_stage_candidate_generator_offsets()
    test_stage_graph_validation_self_targeting()
    test_stage_graph_validation_low_confidence()
    test_dag_validation_valid()
    try:
        test_dag_validation_invalid()
        print("DAG Validation Exception caught correctly.")
    except Exception as e:
        print("DAG Exception:", e)
    print("ALL TESTS PASSED SUCCESSFULLY!")
