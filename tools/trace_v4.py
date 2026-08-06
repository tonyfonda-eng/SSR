import os
import sqlite3

os.environ["ENTITY_ENGINE_VERSION"] = "v4"
import monitor
from tools.replay_pipeline import STAGE_REGISTRY

def mock_ai_event_classification(article, ctx):
    hl = article.get("headline", "")
    if "Acquires" in hl or "Acquisition" in hl or "Buyout" in hl:
        article["_v4_classification"] = "merger" 
    elif "Spin" in hl:
        article["_v4_classification"] = "spin-off"
    elif "Bankrupt" in hl:
        article["_v4_classification"] = "bankruptcy"
    else:
        article["_v4_classification"] = "UNKNOWN"
    article["_v4_confidence"] = 100
    article["_ai_invoked"] = True
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
    print(f"\nTrace (V4): {row[0]}")
    article = {
        "headline": row[0] or "",
        "url": row[1] or "",
        "source": row[2] or "",
        "_target_ticker": row[3] or "UNKNOWN",
        "body": row[0] or ""
    }
    
    ctx = {"ai_router": None}
    
    STAGE_REGISTRY["v4_event_classification"] = mock_ai_event_classification
    STAGE_REGISTRY["v4_entity_resolution"] = mock_ai_entity_resolution
    
    for stage in monitor.execution_order:
        if "dedupe" in stage or "ingestion" in stage: continue
        func = STAGE_REGISTRY.get(stage)
        if not func: continue
        
        p, r = func(article, ctx)
        if p:
            if stage == "v4_opportunity_score":
                print(f"↓\n{stage}\nPASS (Score: {article.get('_v4_opportunity_score', {}).get('total', 0)})")
            elif stage == "v4_event_classification":
                print(f"↓\n{stage}\nPASS ({article.get('_v4_classification', 'UNKNOWN')})")
            elif stage == "v4_trade_hypothesis_generation":
                trades = article.get('_v4_trade_graph', [])
                if trades:
                    print(f"↓\n{stage}\nPASS ({trades[0]['strategy']})")
                else:
                    print(f"↓\n{stage}\nPASS (None)")
            else:
                print(f"↓\n{stage}\nPASS")
        else:
            print(f"↓\n{stage}\nDROPPED: {r}")
            return
            
    print("↓\nRouting\nImmediate Alert")

if __name__ == "__main__":
    rows = get_test_articles()
    for r in rows:
        trace_article(r)
