"""
SSR 2.0 — Main Orchestrator
Highly Granular Adaptive Data-Driven Execution Pipeline (Registry Pattern)
"""

import sys
import logging
import hashlib
import time
import json
import re
from datetime import datetime, timezone

from src.database import (
    initialise_database, get_or_create_event, commit_decision_capsule,
    save_workflow_health, save_exception_log, save_config_snapshot
)

from src.ingestion.scrapers import fetch_all_feeds
from src.ontology import evaluate_ontology
from src.ontology.engine import load_ontology
from src.rules import matches_global_exclusion, matches_issuer_exclusion
from src.rules_engine import evaluate as evaluate_deterministic_rules
from src.ai import extract_target_ticker, classify_event
from src.financials import get_t12_metrics, query_financial_snapshot
from src.alerts.email import send_alert

# --- Frontend Exporter & HTML Generators ---
from src.validation.export_frontend_data import export_archive_json
from src.html_generator import generate_archive_html

from src.config.settings import SHEET_URL
from src.sheets import (
    load_rules, load_global_exclusions, load_document_type_scores,
    load_semantic_concepts, load_event_statuses, get_system_settings,
    load_playbooks, load_sources, load_pipeline_config,
    load_ai_configurations, load_financial_constraints,
    batch_append_daily_memory, append_to_research_queue
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

class PipelineTelemetry:
    def __init__(self):
        self.metrics = {"downloaded": 0, "alerts_generated": 0, "errors": 0}
        self.start_time = time.time()
        self.run_id = f"RUN-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    def track(self, stage: str):
        self.metrics[stage] = self.metrics.get(stage, 0) + 1

    def get_runtime(self):
        return round(time.time() - self.start_time, 2)

# =============================================================================
# HIGHLY GRANULAR ADAPTIVE PIPELINE REGISTRY
# =============================================================================

def stage_dedupe_hash(article: dict, ctx: dict) -> tuple:
    article_body = article.get("body", "")
    article_hash = hashlib.sha256(article_body.encode("utf-8")).hexdigest()
    event_id, is_new = get_or_create_event(article_hash, article_body.encode("utf-8"))
    article["_internal_event_id"] = event_id
    if not is_new: return False, "dropped_hash_duplicate"
    return True, "passed"

def stage_dedupe_issuer_memory(article: dict, ctx: dict) -> tuple:
    return True, "passed"

def stage_exclude_global_keywords(article: dict, ctx: dict) -> tuple:
    if matches_global_exclusion(article.get("body", ""), ctx.get("global_exclusions", [])):
        return False, "dropped_global_keyword"
    return True, "passed"

def stage_exclude_issuer_feed(article: dict, ctx: dict) -> tuple:
    if matches_issuer_exclusion(article.get("source", ""), ctx.get("sources", [])):
        return False, "dropped_issuer_exclusion"
    return True, "passed"

def stage_exclude_source_specific(article: dict, ctx: dict) -> tuple:
    """Drops noise based on the specific behavior/garbage profile of individual feeds."""
    source = article.get("source", "").lower()
    text = article.get("body", "").lower()
    
    # TODO: Migrate these dictionaries to a 'Source Profiles' tab in Google Sheets
    source_noise_profiles = {
        "pr newswire": ["new appointment", "product launch", "esg", "conference", "trade show"],
        "business wire": ["exhibition", "quarterly dividend", "monthly dividend"],
        "globenewswire": ["award", "recognition", "thrilled to welcome"]
    }
    
    for src, noise_keywords in source_noise_profiles.items():
        if src in source:
            for noise in noise_keywords:
                if noise in text:
                    return False, "dropped_source_specific_noise"
    return True, "passed"

# --- ONTOLOGY & RULES (PHASE 2 - MOVED UP TO MINIMIZE CPU LOAD) ---

def stage_ontology_concepts(article: dict, ctx: dict) -> tuple:
    min_score = float(ctx.get("sys_settings", {}).get("MIN_ONTOLOGY_SCORE", 0.65))
    score = evaluate_ontology(article.get("body", ""), ctx.get("semantic_concepts", []))
    if score < min_score: return False, "dropped_ontology_score"
    return True, "passed"

def stage_ontology_status(article: dict, ctx: dict) -> tuple:
    return True, "passed"

def stage_document_scoring(article: dict, ctx: dict) -> tuple:
    return True, "passed"

def stage_regex_rules(article: dict, ctx: dict) -> tuple:
    threshold = int(ctx.get("sys_settings", {}).get("RULE_THRESHOLD", 10))
    active_concepts = [(c.get("Concept_ID", c.get("Concept ID")), c.get("Score", c.get("Weight", 1.0))) for c in ctx.get("semantic_concepts", []) if str(c.get("Active", "TRUE")).upper() == "TRUE"]
    
    rule_results = evaluate_deterministic_rules(
        article={"raw_text": article.get("body", ""), "document_type": article.get("document_type", "Unknown")},
        rules=ctx.get("rules", []),
        document_type_scores=ctx.get("document_type_scores", []),
        ontology_concepts=active_concepts,
        ontology_statuses=ctx.get("event_statuses", []),
        threshold=threshold
    )
    if not rule_results: return False, "dropped_rules_threshold"
    # Save the matched families for playbook eligibility checking
    article["_deterministic_families"] = rule_results if isinstance(rule_results, list) else []
    return True, "passed"

# --- DETERMINISTIC ENTITY STAGES (PHASE 3) ---

def stage_python_issuer_extraction(article: dict, ctx: dict) -> tuple:
    text = article.get("body", "")
    match = re.search(r'([A-Z][A-Za-z0-9\,\.\&\s]{3,40})\s+\([A-Z]{3,6}\s*:\s*[A-Z]{1,5}\)', text[:1000])
    if match:
        article["_deterministic_issuer"] = match.group(1).strip()
    else:
        article["_deterministic_issuer"] = "UNKNOWN"
    return True, "passed"

def stage_python_ticker_lookup(article: dict, ctx: dict) -> tuple:
    text = article.get("body", "")
    match = re.search(r'\b(?:NYSE|NASDAQ|AMEX|OTC|TSX|LSE|NYSE MKT|NYSE ARCA)[^A-Z]{1,3}([A-Z]{1,5})\b', text, re.IGNORECASE)
    if match:
        article["_deterministic_ticker"] = match.group(1).upper()
    else:
        article["_deterministic_ticker"] = "UNKNOWN"
    return True, "passed"

def stage_entity_confidence_gate(article: dict, ctx: dict) -> tuple:
    """Blocks execution if deterministic extraction yields garbage."""
    issuer = article.get("_deterministic_issuer", "UNKNOWN")
    ticker = article.get("_deterministic_ticker", "UNKNOWN")
    
    confidence = 0
    if ticker != "UNKNOWN" and issuer != "UNKNOWN":
        confidence = 100
    elif ticker != "UNKNOWN":
        confidence = 90
    elif issuer != "UNKNOWN":
        confidence = 40
        
    if confidence < 80:
        return False, "dropped_entity_confidence"
        
    return True, "passed"

# --- FINANCIAL CONSTRAINTS (PHASE 4) ---

def stage_financial_market_cap(article: dict, ctx: dict) -> tuple:
    return True, "passed"

def stage_tradeability_check(article: dict, ctx: dict) -> tuple:
    ticker = article.get("_deterministic_ticker", "UNKNOWN")
    if ".PK" in ticker or ".OB" in ticker or ".OTC" in ticker:
        return False, "dropped_untradeable_otc"
    return True, "passed"

def stage_financial_t12_floor(article: dict, ctx: dict) -> tuple:
    ticker = article.get("_deterministic_ticker", "UNKNOWN")
    if ticker != "UNKNOWN":
        metrics = get_t12_metrics(ticker)
        if not metrics.get("valid"): return False, "dropped_financial_t12"
    return True, "passed"

def stage_options_chain_check(article: dict, ctx: dict) -> tuple:
    ticker = article.get("_deterministic_ticker", "UNKNOWN")
    if ticker != "UNKNOWN":
        options_only = str(ctx.get("sys_settings", {}).get("Options Tradable Only", "False")).lower() == "true"
        if options_only:
            snap = query_financial_snapshot(ticker)
            if snap.is_complete and not snap.options_available:
                return False, "dropped_no_options"
    return True, "passed"

def stage_liquidity_check(article: dict, ctx: dict) -> tuple:
    return True, "passed"

# --- PLAYBOOK GATE (PHASE 5 - FINAL DETERMINISTIC FILTER) ---

def stage_playbook_eligibility_check(article: dict, ctx: dict) -> tuple:
    """Drops the article if no active playbook exists for the detected event family."""
    # Ensure there is at least one playbook defined for the deterministic families found
    active_playbooks = [str(p.get("Playbook", "")).lower() for p in ctx.get("playbooks", []) if str(p.get("Active", "TRUE")).upper() == "TRUE"]
    detected_families = [str(f).lower() for f in article.get("_deterministic_families", [])]
    
    # If the rules engine flagged families, but NONE map to a playbook (e.g. Dividend), drop it.
    if detected_families:
        has_playbook = any(family in active_playbooks for family in detected_families)
        if not has_playbook:
            return False, "dropped_no_playbook"
            
    return True, "passed"

# --- THE AI SPECIALIST (PHASE 6 - AMBIGUITY, CLASSIFICATION, SUMMARIZATION ONLY) ---

def stage_ai_ticker_resolution(article: dict, ctx: dict) -> tuple:
    # Deterministic logic already proved highly confident, bypass AI extraction
    if article.get("_deterministic_ticker", "UNKNOWN") != "UNKNOWN":
        article["_ai_ticker"] = article.get("_deterministic_ticker")
        return True, "passed"
        
    ticker = extract_target_ticker(article.get("body", ""))
    if ticker in ["EXHAUSTED", "ERROR", "UNKNOWN"]: 
        return False, "dropped_ai_no_ticker"
    article["_ai_ticker"] = ticker
    return True, "passed"

def stage_ai_event_classification(article: dict, ctx: dict) -> tuple:
    ticker = article.get("_ai_ticker", "UNKNOWN")
    ai_result = classify_event(article.get("body", ""), ticker)
    
    if isinstance(ai_result, str):
        if ai_result in ["EXHAUSTED", "ERROR"]: return False, "ai_exhausted"
        article["_ai_classification"] = ai_result
        article["_ai_confidence"] = 1.0
    else:
        if ai_result.get("status") in ["EXHAUSTED", "ERROR"]: return False, "ai_exhausted"
        article["_ai_classification"] = ai_result.get("classification", "UNKNOWN")
        article["_ai_confidence"] = ai_result.get("confidence", 1.0)
        
    return True, "passed"

def stage_ai_confidence_gate(article: dict, ctx: dict) -> tuple:
    min_conf = float(ctx.get("sys_settings", {}).get("MIN_AI_CONFIDENCE", 0.75))
    if article.get("_ai_confidence", 0.0) < min_conf:
        return False, "dropped_ai_confidence"
    return True, "passed"


STAGE_REGISTRY = {
    "dedupe_hash": stage_dedupe_hash,
    "dedupe_issuer_memory": stage_dedupe_issuer_memory,
    "exclude_global_keywords": stage_exclude_global_keywords,
    "exclude_issuer_feed": stage_exclude_issuer_feed,
    "exclude_source_specific": stage_exclude_source_specific,
    "ontology_concepts": stage_ontology_concepts,
    "ontology_status": stage_ontology_status,
    "document_scoring": stage_document_scoring,
    "regex_rules": stage_regex_rules,
    "python_issuer_extraction": stage_python_issuer_extraction,
    "python_ticker_lookup": stage_python_ticker_lookup,
    "entity_confidence_gate": stage_entity_confidence_gate,
    "financial_market_cap": stage_financial_market_cap,
    "tradeability_check": stage_tradeability_check,
    "financial_t12_floor": stage_financial_t12_floor,
    "options_chain_check": stage_options_chain_check,
    "liquidity_check": stage_liquidity_check,
    "playbook_eligibility_check": stage_playbook_eligibility_check,
    "ai_ticker_resolution": stage_ai_ticker_resolution,
    "ai_event_classification": stage_ai_event_classification,
    "ai_confidence_gate": stage_ai_confidence_gate
}

def process_article(article: dict, telemetry: PipelineTelemetry, config_manifest: dict, manifest_hash: str):
    settings = config_manifest.get("settings", [])
    ctx = config_manifest.copy()
    ctx["sys_settings"] = settings[0] if settings else {}
    
    raw_pipeline_sheet = config_manifest.get("pipeline", [])
    if raw_pipeline_sheet:
        sorted_stages = sorted([s for s in raw_pipeline_sheet if str(s.get("Active", "TRUE")).upper() == "TRUE"], key=lambda x: int(x.get("Order", 99)))
        execution_order = [s.get("Stage_ID") for s in sorted_stages]
    else:
        # Fallback Strict DAG
        execution_order = [
            "dedupe_hash", 
            "dedupe_issuer_memory", 
            "exclude_global_keywords", 
            "exclude_issuer_feed", 
            "exclude_source_specific",
            "ontology_concepts", 
            "ontology_status", 
            "document_scoring", 
            "regex_rules", 
            "python_issuer_extraction", 
            "python_ticker_lookup", 
            "entity_confidence_gate",
            "financial_market_cap",
            "tradeability_check", 
            "financial_t12_floor", 
            "options_chain_check", 
            "liquidity_check", 
            "playbook_eligibility_check",
            "ai_ticker_resolution", 
            "ai_event_classification", 
            "ai_confidence_gate"
        ]

    for stage_name in execution_order:
        telemetry.track(f"entered_{stage_name}")
        
        stage_func = STAGE_REGISTRY.get(stage_name.lower())
        if not stage_func: 
            logger.warning(f"Configuration requested unknown pipeline stage: {stage_name}")
            continue
        passed, drop_reason = stage_func(article, ctx)
        if not passed:
            telemetry.track(drop_reason)
            return False 
            
        telemetry.track(f"survived_{stage_name}")
            
    telemetry.track("alerts_generated")
    event_id = article.get("_internal_event_id", "UNKNOWN")
    ticker = article.get("_ai_ticker", "UNKNOWN")
    event_family = article.get("_ai_classification", "Corporate Announcement")
    
    decision_capsule = {
        "decision_id": f"DEC-{hashlib.md5(f'{event_id}:{ticker}'.encode()).hexdigest()[:12].upper()}",
        "event_id": event_id,
        "manifest_hash": manifest_hash,
        "runtime_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT"),
        "detection_outcome": "DETECTED",
        "terminal_stage": "AI_APPROVED",
        "headline": article.get("headline", "Corporate Announcement"),
        "url": article.get("url", "UNKNOWN"),
        "ai_core_inference": {
            "aggregate_confidence": article.get("_ai_confidence", 1.0),
            "parsed_structural_properties": {"ticker": ticker}
        }
    }
    
    commit_decision_capsule(decision_capsule)
    logger.info(f"[ALERT GENERATED] {ticker} - {event_family}")
    
    try:
        if ticker != "UNKNOWN":
            batch_append_daily_memory(SHEET_URL, [ticker])
            
        append_to_research_queue(SHEET_URL, {
            "timestamp": decision_capsule["runtime_timestamp"],
            "ticker": ticker,
            "issuer": ticker,
            "event_family": event_family,
            "url": decision_capsule["url"],
            "status": "Alert Dispatched"
        })
    except Exception as e:
        logger.error(f"[SHEETS SYNC FAULT] Failed to update Daily Memory or Research Queue: {e}")

    try:
        send_alert(decision_capsule)
    except Exception as e:
        logger.error(f"[EMAIL DISPATCH FAILED] Unable to send alert for {ticker}: {e}")
        
    return True

def main():
    logger.info("Initializing SSR 2.0 Highly Granular Pipeline...")
    try:
        initialise_database()
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        sys.exit(1)

    telemetry = PipelineTelemetry()
    
    try:
        load_ontology(SHEET_URL)
        config_manifest = {
            "rules": load_rules(SHEET_URL),
            "global_exclusions": load_global_exclusions(SHEET_URL),
            "sources": load_sources(SHEET_URL),
            "document_type_scores": load_document_type_scores(SHEET_URL),
            "semantic_concepts": load_semantic_concepts(SHEET_URL),
            "event_statuses": load_event_statuses(SHEET_URL),
            "settings": get_system_settings(SHEET_URL),
            "playbooks": load_playbooks(SHEET_URL),
            "pipeline": load_pipeline_config(SHEET_URL),
            "ai_configs": load_ai_configurations(SHEET_URL),
            "financial_rules": load_financial_constraints(SHEET_URL)
        }
        
        config_json = json.dumps(config_manifest, sort_keys=True)
        manifest_hash = f"CFG-{hashlib.sha256(config_json.encode('utf-8')).hexdigest()[:12].upper()}"
        save_config_snapshot(manifest_hash, telemetry.run_id, config_json)
        logger.info(f"Locked Immutable Configuration Manifest: {manifest_hash}")
    except Exception as e:
        logger.critical(f"Failed to fetch Configuration Manifest: {e}")
        sys.exit(1)
    
    try:
        articles = fetch_all_feeds(config_manifest.get("sources", [])) 
        telemetry.metrics["downloaded"] = len(articles)

        for article in articles:
            try:
                process_article(article, telemetry, config_manifest, manifest_hash)
            except Exception as e:
                logger.error(f"Error processing article: {e}")
                telemetry.track("errors")
    except Exception as e:
        logger.critical(f"Fatal error in main pipeline loop: {e}")
    
    finally:
        logger.info("Pipeline execution finished. Generating observability exports...")
        
        logger.info("\n=== 📉 PIPELINE STAGE FUNNEL 📉 ===")
        for key, count in sorted(telemetry.metrics.items()):
            logger.info(f"  {key}: {count}")
        logger.info("===================================\n")
        
        health_payload = {
            "run_id": telemetry.run_id,
            "total_scanned": telemetry.metrics.get("downloaded", 0),
            "articles": telemetry.metrics.get("alerts_generated", 0),
            "errors": telemetry.metrics.get("errors", 0) + telemetry.metrics.get("ai_exhausted", 0),
            "runtime": telemetry.get_runtime(),
            "funnel": telemetry.metrics
        }
        save_workflow_health(health_payload)
        
        try:
            logger.info("Dumping Ledger to archive_data.json...")
            export_archive_json("docs/archive_data.json")
            
            logger.info("Rebuilding HTML Dashboards...")
            generate_archive_html("docs/archive.html")
        except Exception as e:
            logger.error(f"Frontend Data & HTML Export failed: {e}")

if __name__ == "__main__":
    main()