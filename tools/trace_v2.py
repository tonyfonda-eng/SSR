import os
import sqlite3

os.environ["ENTITY_ENGINE_VERSION"] = "1"
import monitor
from tools.replay_pipeline import STAGE_REGISTRY

def mock_ai_event_classification(article, ctx):
    hl = article.get("headline", "")
    if "Acquires" in hl or "Acquisition" in hl or "Buyout" in hl:
        article["_ai_classification"] = "merger" 
    elif "Spin" in hl:
        article["_ai_classification"] = "spin-off"
    elif "Bankrupt" in hl:
        article["_ai_classification"] = "bankruptcy"
    else:
        article["_ai_classification"] = "UNKNOWN"
    return True, "passed"

def mock_ai_entity_resolution(article, ctx):
    hl = article.get("headline", "")
    entities = []
    
    if "Emerson" in hl and "Glue" in hl:
        entities.append({"ticker": "EMR", "role": "acquirer", "is_public": True, "options_available": True})
        entities.append({"ticker": "GLUE", "role": "target", "is_public": False, "options_available": False})
    elif "NetApp" in hl and "JetStream" in hl:
        entities.append({"ticker": "NTAP", "role": "acquirer", "is_public": True, "options_available": True})
        entities.append({"ticker": "JET", "role": "target", "is_public": False, "options_available": False})
    elif "Veralto" in hl and "Alfaa" in hl:
        entities.append({"ticker": "VLTO", "role": "acquirer", "is_public": True, "options_available": True})
        entities.append({"ticker": "ALFA", "role": "target", "is_public": False, "options_available": False})
    elif "Newmark" in hl and "L+P" in hl:
        entities.append({"ticker": "NMRK", "role": "acquirer", "is_public": True, "options_available": True})
        entities.append({"ticker": "LP", "role": "target", "is_public": False, "options_available": False})
    else:
        entities.append({"ticker": article.get("_target_ticker", "UNKNOWN"), "role": "target", "is_public": True, "options_available": True})
        
    article["_entities"] = entities
    article["_ai_invoked"] = True
    return True, "passed"

def get_test_articles():
    conn = sqlite3.connect("ssr_observability.db")
    c = conn.cursor()
    
    targets = ["Emerson Acquires Glue", "NetApp Acquires JetStream", "Veralto Acquires Alfaa", "Newmark Acquires"]
    
    results = []
    for t in targets:
        c.execute("""
            SELECT headline, url, source, ticker, event_family 
            FROM article_screening_log 
            WHERE headline LIKE ? 
            ORDER BY timestamp DESC LIMIT 1
        """, (f"%{t}%",))
        row = c.fetchone()
        if row:
            results.append(row)
    conn.close()
    return results

def trace_article(row):
    print(f"\nTracing: {row[0]}")
    article = {
        "headline": row[0] or "",
        "url": row[1] or "",
        "source": row[2] or "",
        "_target_ticker": row[3] or "UNKNOWN",
        "_ai_classification": row[4] or "",
        "body": row[0] or ""
    }
    
    ctx = {"ai_router": None}
    
    STAGE_REGISTRY["python_issuer_extraction"] = mock_ai_entity_resolution
    STAGE_REGISTRY["ai_event_classification"] = mock_ai_event_classification
    
    execution_order = [
        "dedupe_hash", "dedupe_issuer_memory", "exclude_global_keywords", 
        "exclude_issuer_feed", "exclude_source_specific", "ontology_concepts", 
        "ontology_status", "document_scoring", "regex_rules", 
        "python_issuer_extraction", "candidate_generator", "ambiguity_gate", 
        "ai_entity_resolution", "graph_validation", "ai_event_classification", "ai_confidence_gate", 
        "investment_universe_mapping", "strategy_selection", "investment_candidate_selection",
        "entity_confidence_gate", "financial_market_cap", "tradeability_check", 
        "financial_t12_floor", "options_chain_check", "liquidity_check", 
        "playbook_eligibility_check"
    ]
    pb_gates = ["playbook_eligibility_check", "financial_t12_floor", "options_chain_check"]
    ai_idx = execution_order.index("ai_event_classification")
    for pg in pb_gates:
        if pg in execution_order:
            pg_idx = execution_order.index(pg)
            if pg_idx < ai_idx:
                execution_order.remove(pg)
                ai_idx = execution_order.index("ai_event_classification")
                
    for stage in execution_order:
        if "dedupe" in stage: continue
        func = STAGE_REGISTRY.get(stage)
        if not func: continue
        
        p, r = func(article, ctx)
        if p:
            print(f"↓\n{stage}\nPASS")
        else:
            print(f"↓\n{stage}\nDROPPED: {r}")
            return
            
    print("↓\nRouting\nImmediate Alert")

if __name__ == "__main__":
    rows = get_test_articles()
    for r in rows:
        trace_article(r)
