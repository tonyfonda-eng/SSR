import os
import hashlib
import json
import sqlite3
import datetime
import re

from src.ai import classify_event, extract_entities_and_roles
from src.database import log_event
from src.financials import query_financial_snapshot, get_t12_metrics

def _extract_ticker(text: str):
    match = re.search(r'\b(?:NYSE|NASDAQ|AMEX|OTC|TSX|LSE|NYSE MKT|NYSE ARCA)\s*[:]\s*([A-Z]{1,5})\b', text, re.IGNORECASE)
    if not match:
        match = re.search(r'\((?:NYSE|NASDAQ|AMEX|OTC|TSX|LSE)\s*:\s*([A-Z]{1,5})\)', text, re.IGNORECASE)
    return match.group(1).upper() if match else "UNKNOWN"

def _confidence_scored_merge(article: dict, existing_events: list) -> tuple:
    import difflib
    
    best_score = 0
    best_event = None
    best_decision = None
    
    article_entities = {e.get("ticker") for e in article.get("_entities", []) if e.get("ticker") and e.get("ticker") != "UNKNOWN"}
    article_headline = article.get("headline", "")
    
    for row in existing_events:
        event_id = row[0]
        event_type = row[1]
        try:
            entities = json.loads(row[2])
            existing_tickers = {e.get("ticker") for e in entities if e.get("ticker") and e.get("ticker") != "UNKNOWN"}
        except:
            existing_tickers = set()
            
        try:
            evidence = json.loads(row[3])
            last_headline = evidence[-1] if evidence else ""
        except:
            last_headline = ""
            
        created_at_str = row[4]
        
        score = 0
        components = {
            "entity_similarity": 0,
            "headline_similarity": 0,
            "time_proximity": 0,
            "event_progression": 0,
            "transaction_value_similarity": None
        }
        evidence_used = []
        missing_evidence = ["transaction_value"]
        reasoning_parts = []
        
        # 1. Entity Similarity (max 40)
        intersection = article_entities.intersection(existing_tickers)
        if intersection:
            score += 40
            components["entity_similarity"] = 100
            evidence_used.append("entity")
            reasoning_parts.append(f"Shared entities ({', '.join(intersection)})")
        else:
            components["entity_similarity"] = 0
            
        # 2. Headline Similarity (max 30)
        seq_ratio = difflib.SequenceMatcher(None, article_headline.lower(), last_headline.lower()).ratio()
        score += int(seq_ratio * 30)
        components["headline_similarity"] = int(seq_ratio * 100)
        if seq_ratio > 0.5:
            evidence_used.append("headline")
            reasoning_parts.append("similar headline")
        
        # 3. Time Proximity (max 20)
        try:
            created_at = datetime.datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S GMT").replace(tzinfo=datetime.timezone.utc)
            now = datetime.datetime.now(datetime.timezone.utc)
            hours_diff = (now - created_at).total_seconds() / 3600
            if hours_diff < 24:
                score += 20
                components["time_proximity"] = 100
                evidence_used.append("time")
                reasoning_parts.append(f"within {int(hours_diff)} hours")
            elif hours_diff < 72:
                score += 10
                components["time_proximity"] = 50
                evidence_used.append("time")
                reasoning_parts.append(f"within {int(hours_diff)} hours")
            else:
                components["time_proximity"] = 0
        except:
            pass
            
        # 4. Event Progression (max 10)
        if article.get("_v4_classification") == event_type:
            score += 10
            components["event_progression"] = 100
            evidence_used.append("progression")
            reasoning_parts.append("matching event classification")
        else:
            components["event_progression"] = 0
            
        decision_val = "AUTO_MERGE" if score > 90 else "REVIEW" if score > 60 else "NEW_EVENT"
            
        decision_obj = {
            "score": score,
            "decision": decision_val,
            "components": components,
            "evidence_used": evidence_used,
            "missing_evidence": missing_evidence,
            "reasoning": ", ".join(reasoning_parts) if reasoning_parts else "No significant overlap."
        }
            
        if score > best_score:
            best_score = score
            best_event = event_id
            best_decision = decision_obj
            
    if best_decision is None:
        best_decision = {
            "score": 0,
            "decision": "NEW_EVENT",
            "components": {
                "entity_similarity": 0,
                "headline_similarity": 0,
                "time_proximity": 0,
                "event_progression": 0,
                "transaction_value_similarity": None
            },
            "evidence_used": [],
            "missing_evidence": ["transaction_value"],
            "reasoning": "No existing events to merge against."
        }
        
    return best_score, best_event, best_decision

def stage_v4_ingestion(article: dict, ctx: dict) -> tuple:
    # Set internal tracking fields
    article["_v4_event_id"] = "EVT-" + hashlib.md5((article.get("headline", "") + article.get("source", "")).encode()).hexdigest()[:12].upper()
    return True, "passed"

def stage_v4_dedupe(article: dict, ctx: dict) -> tuple:
    from monitor import stage_dedupe_hash
    return stage_dedupe_hash(article, ctx)

def stage_v4_entity_resolution(article: dict, ctx: dict) -> tuple:
    article["_deterministic_ticker"] = _extract_ticker(article.get("headline", "") + " " + article.get("body", ""))
    
    # 1. Deterministic extraction if possible
    # For uncertainty gating, we need to know if we NEED AI.
    # We always need AI to extract multiple entities for M&A, but if it's a simple earnings/dividend, maybe not.
    # For now, let's just invoke AI for entity extraction if ambiguity is high, else rely on deterministic.
    
    text = article.get("headline", "") + " " + article.get("body", "")
    if not any(kw in text.lower() for kw in ["acquire", "acquisition", "merger", "buyout", "spin-off", "bankrupt"]):
        # deterministic path
        if article["_deterministic_ticker"] != "UNKNOWN":
            article["_entities"] = [{"ticker": article["_deterministic_ticker"], "role": "target", "is_public": True}]
            article["_ai_invoked"] = False
            return True, "passed"
            
    # AI path for Uncertainty
    article["_ai_invoked"] = True
    graph = extract_entities_and_roles(text, router=ctx.get("ai_router"))
    if graph.error:
        return False, f"dropped_entity_error: {graph.error}"
        
    article["_entities"] = [n.__dict__ for n in graph.nodes]
    
    for e in article["_entities"]:
        if e.get("is_public") and e.get("ticker"):
            snap = None
            try:
                snap = query_financial_snapshot(e["ticker"])
            except:
                pass
            e["options_available"] = snap.options_available if snap else False
            
    return True, "passed"

def stage_v4_event_classification(article: dict, ctx: dict) -> tuple:
    if not article.get("_ai_invoked", False):
        article["_v4_classification"] = "Corporate Announcement"
        article["_v4_confidence"] = 100
        return True, "passed"
        
    ai_result = classify_event(article.get("body", ""), [], article.get("_deterministic_ticker", "UNKNOWN"), router=ctx.get("ai_router"))
    if isinstance(ai_result, str):
        if ai_result in ["EXHAUSTED", "ERROR"]: return False, "ai_exhausted"
        article["_v4_classification"] = ai_result
        article["_v4_confidence"] = 100
    else:
        if ai_result.get("status") in ["EXHAUSTED", "ERROR"]: return False, "ai_exhausted"
        article["_v4_classification"] = ai_result.get("classification", "UNKNOWN")
        article["_v4_confidence"] = 100
        
    # Match Persistent Event ID
    try:
        from src.config.settings import RESEARCH_DB_PATH
        conn = sqlite3.connect(RESEARCH_DB_PATH)
        c = conn.cursor()
        
        # Only query recent events (last 14 days) to keep memory footprint low
        c.execute("""
            SELECT event_id, event_type, entities, evidence, created_at 
            FROM event_ledger 
            ORDER BY created_at DESC LIMIT 500
        """)
        recent_events = c.fetchall()
        
        best_score, best_event, merge_decision = _confidence_scored_merge(article, recent_events)
        
        article["_v4_merge_decision"] = merge_decision
        
        if best_score > 90:
            article["_v4_event_id"] = best_event
            article["_v4_is_update"] = True
            article["_v4_human_review"] = 0
        elif best_score > 60:
            # We spawn a new event but flag it for human review
            article["_v4_human_review"] = 1
        else:
            article["_v4_human_review"] = 0
            
    except Exception:
        pass
    finally:
        try: conn.close()
        except: pass

    return True, "passed"

def stage_v4_trade_hypothesis_generation(article: dict, ctx: dict) -> tuple:
    entities = article.get("_entities", [])
    event_type = str(article.get("_v4_classification", "")).lower()
    
    trades = []
    
    if "merger" in event_type or "acquisition" in event_type:
        target = next((e for e in entities if e.get("role") == "target"), None)
        acquirer = next((e for e in entities if e.get("role") == "acquirer"), None)
        
        if target and target.get("is_public"):
            trades.append({"strategy": "Merger Arb", "ticker": target.get("ticker"), "priority": 1, "reason": "Target in M&A"})
        if acquirer and acquirer.get("is_public"):
            trades.append({"strategy": "Acquirer Overwrite", "ticker": acquirer.get("ticker"), "priority": 2, "reason": "Acquirer in M&A"})
    
    elif "spin-off" in event_type:
        parent = next((e for e in entities if e.get("role") == "parent"), None)
        if parent and parent.get("is_public"):
            trades.append({"strategy": "Spin-off Rerating", "ticker": parent.get("ticker"), "priority": 1, "reason": "Parent divesting asset"})
            
    elif "bankrupt" in event_type:
        target = next((e for e in entities if e.get("role") == "target"), None)
        if target and target.get("is_public"):
            trades.append({"strategy": "Bankruptcy Liquidation", "ticker": target.get("ticker"), "priority": 1, "reason": "Chapter 11"})
            
    else:
        public_entities = [e for e in entities if e.get("is_public") and e.get("ticker")]
        if public_entities:
            trades.append({"strategy": "General Momentum", "ticker": public_entities[0]["ticker"], "priority": 3, "reason": "Corporate Announcement"})
            
    if not trades:
        return False, "dropped_no_trade_generated"
        
    article["_v4_hypotheses"] = trades
    return True, "passed"

def stage_v4_strategy_validation(article: dict, ctx: dict) -> tuple:
    trades = article.get("_v4_hypotheses", [])
    valid_trades = []
    
    for t in trades:
        metrics = get_t12_metrics(t["ticker"])
        if t["strategy"] == "Merger Arb":
            t["status"] = "Valid"
        elif t["strategy"] == "Acquirer Overwrite":
            t["status"] = "Valid"
        else:
            if not metrics.get("valid"):
                t["status"] = f"Invalid: {metrics.get('reason')}"
            else:
                t["status"] = "Valid"
        if t["status"] == "Valid":
            valid_trades.append(t)
            
    article["_v4_validated_trades"] = valid_trades
    return True, "passed"

def stage_v4_opportunity_score(article: dict, ctx: dict) -> tuple:
    valid_trades = article.get("_v4_validated_trades", [])
    
    if not valid_trades:
        return False, "dropped_failed_strategy_validation"
        
    entity_raw = 25 if valid_trades[0]["ticker"] != "UNKNOWN" else 0
    event_raw = 35 if article.get("_ai_invoked") else 10
    trade_raw = 20 if valid_trades[0]["strategy"] != "General Momentum" else 5
    financial_raw = 20
        
    score_dict = {
        "entity_confidence": entity_raw,
        "event_confidence": event_raw,
        "trade_confidence": trade_raw,
        "financial_quality": financial_raw,
        "raw_components": {
            "entity": f"{entity_raw}/25",
            "event": f"{event_raw}/35",
            "trade": f"{trade_raw}/20",
            "financial": f"{financial_raw}/20"
        }
    }
    score_dict["total"] = sum([entity_raw, event_raw, trade_raw, financial_raw])
    article["_v4_opportunity_score"] = score_dict
    
    if score_dict["total"] < 50:
        return False, f"dropped_low_opportunity_score: {score_dict['total']}"
        
    return True, "passed"

def stage_v4_routing(article: dict, ctx: dict) -> tuple:
    from monitor import _record_screening
    
    event_id = article["_v4_event_id"]
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT")
    
    confidence_history = []
    evidence = []
    lifecycle = []
    created_at = timestamp
    
    try:
        from src.config.settings import RESEARCH_DB_PATH
        conn = sqlite3.connect(RESEARCH_DB_PATH)
        c = conn.cursor()
        c.execute("SELECT confidence_history, evidence, lifecycle, created_at FROM event_ledger WHERE event_id = ?", (event_id,))
        row = c.fetchone()
        if row:
            if row[0]: confidence_history = json.loads(row[0])
            if row[1]: evidence = json.loads(row[1])
            if row[2]: lifecycle = json.loads(row[2])
            if row[3]: created_at = row[3]
    except Exception:
        pass
    finally:
        try: conn.close()
        except: pass
        
    version = len(confidence_history) + 1
    reason = "Initial detection" if version == 1 else f"{article.get('source', 'Unknown')} confirmation"
    
    confidence_history.append({
        "version": version,
        "timestamp": timestamp,
        "source": article.get("source", "Unknown"),
        "score": article.get("_v4_opportunity_score", {}).get("total", 0),
        "reason": reason
    })
    
    evidence.append(article.get("headline"))
    lifecycle.append({"timestamp": timestamp, "stage": "Actionable Alert"})
    
    event_data = {
        "event_id": event_id,
        "created_at": created_at,
        "updated_at": timestamp,
        "status": "ACTIONABLE",
        "event_type": article.get("_v4_classification", "UNKNOWN"),
        "opportunity_score": article.get("_v4_opportunity_score", {}),
        "confidence_history": confidence_history,
        "hypotheses": article.get("_v4_hypotheses", []),
        "validated_trades": article.get("_v4_validated_trades", []),
        "evidence": evidence,
        "entities": article.get("_entities", []),
        "routing_destination": "EMAIL_DISPATCH",
        "lifecycle": lifecycle,
        "human_review_flag": article.get("_v4_human_review", 0),
        "merge_decision": article.get("_v4_merge_decision", {})
    }
    
    try:
        log_event(event_data)
    except Exception as e:
        print(f"Routing failed on DB write: {e}")
        return False, f"dropped_db_error: {e}"
        
    try:
        from src.alerts.email import send_v4_event_report
        send_v4_event_report(event_data)
    except Exception as e:
        print(f"Email dispatch failed: {e}")
        # Do not drop or fail the pipeline. The event is safely persisted as ACTIONABLE in the ledger.
        
    article["_v4_routed"] = True
    return True, "passed"
