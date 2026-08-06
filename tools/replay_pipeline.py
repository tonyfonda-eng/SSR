import sys
import os
import json
import sqlite3
import datetime
import time

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import monitor
from src.database import RESEARCH_DB_PATH
from monitor import STAGE_REGISTRY, PipelineTelemetry

# Monkey-patch database writes to prevent polluting live DB
monitor.log_article_screening = lambda *args, **kwargs: None
monitor.commit_decision_capsule = lambda *args, **kwargs: None

# Disable shadow mode for replay
os.environ["ENTITY_ENGINE_VERSION"] = "2.1"

# The new DAG order
execution_order = [
    "dedupe_hash", "dedupe_issuer_memory", "exclude_global_keywords", 
    "exclude_issuer_feed", "exclude_source_specific", "ontology_concepts", 
    "candidate_generator", "ambiguity_gate", "entity_resolution",
    "event_suspicion", "source_quota_gate", "ai_event_classification", 
    "ai_confidence_gate", "trade_generation",
    "strategy_financial_gate", "opportunity_scoring"
]

def load_config_manifest():
    from src.config.settings import SHEET_URL, get_system_settings
    from src.sheets import (
        load_rules, load_global_exclusions, load_sources, load_document_type_scores,
        load_semantic_concepts, load_event_statuses, load_playbooks,
        load_pipeline_config, load_ai_configurations, load_financial_constraints
    )
    from src.ontology.engine import load_ontology
    
    load_ontology(SHEET_URL)
    return {
        "rules": load_rules(SHEET_URL),
        "global_exclusions": load_global_exclusions(SHEET_URL),
        "sources": load_sources(SHEET_URL),
        "document_type_scores": load_document_type_scores(SHEET_URL),
        "semantic_concepts": load_semantic_concepts(SHEET_URL),
        "event_statuses": load_event_statuses(SHEET_URL),
        "settings": [get_system_settings(SHEET_URL)],
        "playbooks": load_playbooks(SHEET_URL),
        "pipeline": load_pipeline_config(SHEET_URL),
        "ai_configs": load_ai_configurations(SHEET_URL),
        "financial_rules": load_financial_constraints(SHEET_URL)
    }

def run_replay():
    print("[*] Starting Replay Simulator...")
    print(f"[*] Replay DAG: {' -> '.join(execution_order)}")
    
    conn = sqlite3.connect(RESEARCH_DB_PATH)
    cursor = conn.cursor()
    
    # Fetch payload from article_screening_log
    cursor.execute("SELECT headline, url, source, ticker, event_family FROM article_screening_log ORDER BY timestamp DESC LIMIT 2000")
    rows = cursor.fetchall()
    
    print(f"[*] Fetched {len(rows)} raw articles for replay.")
    
    manifest = load_config_manifest()
    telemetry = PipelineTelemetry()
    
    ctx = {
        "sys_settings": manifest.get("settings", [])[0] if manifest.get("settings") else {},
        "semantic_concepts": manifest.get("semantic_concepts", []),
        "event_statuses": manifest.get("event_statuses", []),
        "rules": manifest.get("rules", []),
        "global_exclusions": manifest.get("global_exclusions", []),
        "document_type_scores": manifest.get("document_type_scores", []),
        "playbooks": manifest.get("playbooks", []),
        "financial_rules": manifest.get("financial_rules", []),
        "ai_router": None,
        "telemetry": telemetry
    }
    
    results = {
        "survived": 0,
        "dropped_deterministic_gate": 0,
        "dropped_financial_gate": 0,
        "ai_calls_simulated": 0,
        "recovered_ma": 0,
        "recovered_activism": 0,
        "recovered_spinoffs": 0,
        "recovered_bankruptcies": 0
    }
    
    def mock_ai_event_classification(article, ctx):
        article["_ai_classification"] = "merger" # Fake classification to test financial gates
        results["ai_calls_simulated"] += 1
        return True, "passed"
        
    STAGE_REGISTRY["ai_event_classification"] = mock_ai_event_classification

    for idx, row in enumerate(rows):
        if idx > 0 and idx % 200 == 0:
            print(f"    ... processed {idx} articles")
            
        article = {
            "headline": row[0] or "",
            "url": row[1] or "",
            "source": row[2] or "",
            "_target_ticker": row[3] or "UNKNOWN",
            "_ai_classification": row[4] or "",
            "body": row[0] or "" # Fallback to headline since body isn't saved
        }
                
        passed = True
        drop_stage = None
        
        for stage in execution_order:
            func = STAGE_REGISTRY.get(stage)
            if not func: continue
            
            p, r = func(article, ctx)
            if not p:
                passed = False
                drop_stage = stage
                break
                
        if passed:
            results["survived"] += 1
            if article.get("_opportunity_score", 0.0) >= 80:
                cls = str(article.get("_ai_classification", "")).lower()
                if "merger" in cls or "acquisition" in cls or "takeover" in cls:
                    results["recovered_ma"] += 1
                elif "activis" in cls:
                    results["recovered_activism"] += 1
                elif "spin-off" in cls or "spinoff" in cls:
                    results["recovered_spinoffs"] += 1
                elif "bankrupt" in cls or "chapter 11" in cls:
                    results["recovered_bankruptcies"] += 1
        else:
            if drop_stage not in results:
                results[drop_stage] = 0
            results[drop_stage] += 1

    print("\n" + "="*50)
    print("REPLAY SIMULATOR RESULTS")
    print("="*50)
    print(f"Total articles processed: {len(rows)}")
    print(f"Survived (Alert Generated): {results['survived']}")
    print(f"Recovered M&A: {results['recovered_ma']}")
    print(f"Recovered Activism: {results['recovered_activism']}")
    print(f"Recovered Spin-offs: {results['recovered_spinoffs']}")
    print(f"Recovered Bankruptcies: {results['recovered_bankruptcies']}")
    for k, v in results.items():
        if k not in ["survived", "ai_calls_simulated", "recovered_ma", "recovered_activism", "recovered_spinoffs", "recovered_bankruptcies"]:
            print(f"Dropped at {k}: {v}")
    print(f"Simulated AI Calls: {results['ai_calls_simulated']}")
    print("="*50)

if __name__ == "__main__":
    run_replay()
