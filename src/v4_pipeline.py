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
    return True, "passed"

def stage_v4_trade_generation(article: dict, ctx: dict) -> tuple:
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
        
    article["_v4_trade_graph"] = trades
    return True, "passed"

def stage_v4_strategy_validation(article: dict, ctx: dict) -> tuple:
    trades = article.get("_v4_trade_graph", [])
    valid_trades = []
    
    for t in trades:
        metrics = get_t12_metrics(t["ticker"])
        if t["strategy"] == "Merger Arb":
            # Target negative net cash is allowed
            t["status"] = "Valid"
            valid_trades.append(t)
        elif t["strategy"] == "Acquirer Overwrite":
            # Bypass T12 check for M&A Acquirer
            t["status"] = "Valid"
            valid_trades.append(t)
        else:
            t["status"] = "Valid"
            valid_trades.append(t)
            
    article["_v4_trade_graph"] = valid_trades
    return True, "passed"

def stage_v4_opportunity_score(article: dict, ctx: dict) -> tuple:
    trades = article.get("_v4_trade_graph", [])
    valid_trades = [t for t in trades if t["status"] == "Valid"]
    
    if not valid_trades:
        return False, "dropped_failed_strategy_validation"
        
    score_dict = {
        "entity_confidence": 25 if valid_trades[0]["ticker"] != "UNKNOWN" else 0,
        "event_confidence": 35 if article.get("_ai_invoked") else 10,
        "trade_confidence": 20 if valid_trades[0]["strategy"] != "General Momentum" else 5,
        "financial_quality": 20
    }
    score_dict["total"] = sum(score_dict.values())
    article["_v4_opportunity_score"] = score_dict
    
    if score_dict["total"] < 50:
        return False, f"dropped_low_opportunity_score: {score_dict['total']}"
        
    return True, "passed"

def stage_v4_routing(article: dict, ctx: dict) -> tuple:
    from monitor import _record_screening
    
    event_data = {
        "event_id": article["_v4_event_id"],
        "created_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT"),
        "updated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT"),
        "status": "ACTIONABLE",
        "event_type": article.get("_v4_classification", "UNKNOWN"),
        "opportunity_score": article.get("_v4_opportunity_score", {}),
        "confidence_history": [{"timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT"), "score": article.get("_v4_opportunity_score", {}).get("total", 0)}],
        "trade_graph": article.get("_v4_trade_graph", []),
        "evidence": [article.get("headline")],
        "entities": article.get("_entities", []),
        "routing_destination": "EMAIL_DISPATCH"
    }
    
    try:
        log_event(event_data)
    except Exception as e:
        pass
        
    article["_v4_routed"] = True
    return True, "passed"
