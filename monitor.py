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
import subprocess
from datetime import datetime, timezone

from src.database import (
    initialise_database, get_or_create_event, commit_decision_capsule,
    save_workflow_health, save_exception_log, save_config_snapshot,
    log_article_screening, log_audit_source_metrics, log_audit_ai_metrics, log_audit_event
)

from src.validation.export_frontend_data import export_archive_json, export_screening_json
try:
    from src.validation.export_screening_log import export_screening_log
except ImportError:
    export_screening_log = export_screening_json

from src.audit.realtime_audit import export_realtime_audit

from src.html_generator import (
    generate_dashboard_html,
    generate_decision_analytics_html, generate_screening_log_html,
    generate_pipeline_health_html
)

from src.ingestion.scrapers import fetch_all_feeds
from src.ontology import evaluate_ontology, evaluate_ontology_rich
from src.ontology.engine import load_ontology
from src.rules import matches_global_exclusion, matches_issuer_exclusion
from src.rules_engine import evaluate as evaluate_deterministic_rules
from src.ai import extract_entities_and_roles, classify_event
from src.providers.router import ProviderRouter
from src.financials import get_t12_metrics, query_financial_snapshot
from src.alerts.email import send_alert
import os

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
        self.run_id = f"RUN-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        self.start_time = time.time()
        
        # Volumetric counters
        self.metrics = {"downloaded": 0, "alerts_generated": 0, "errors": 0}
        
        # High-resolution metrics ledger for cost accounting
        self.stage_analytics = {}

    def track_stage_performance(self, stage: str, outcome: str, cpu_ns: int, network_ns: int, api_calls: int, reason: str = "N/A"):
        """Records precise granular economics for pipeline observability."""
        if stage not in self.stage_analytics:
            self.stage_analytics[stage] = {
                "entered": 0,
                "passed": 0,
                "rejected": 0,
                "cpu_ms": 0.0,
                "network_ms": 0.0,
                "api_calls": 0,
                "drop_reasons": {}
            }
            
        metrics = self.stage_analytics[stage]
        metrics["entered"] += 1
        
        if outcome == "passed":
            metrics["passed"] += 1
        else:
            metrics["rejected"] += 1
            if reason != "N/A":
                metrics["drop_reasons"][reason] = metrics["drop_reasons"].get(reason, 0) + 1
            
        metrics["cpu_ms"] += round(cpu_ns / 1_000_000, 3)
        metrics["network_ms"] += round(network_ns / 1_000_000, 3)
        metrics["api_calls"] += api_calls

    def track(self, key: str):
        """Fallback for global counters."""
        self.metrics[key] = self.metrics.get(key, 0) + 1

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
    matched, keyword = matches_global_exclusion(article.get("body", ""), ctx.get("global_exclusions", []))
    if matched:
        return False, f"dropped_global_keyword: {keyword}"
    return True, "passed"

def stage_exclude_issuer_feed(article: dict, ctx: dict) -> tuple:
    if matches_issuer_exclusion(article.get("source", ""), ctx.get("sources", [])):
        return False, "dropped_issuer_exclusion"
    return True, "passed"

def stage_exclude_source_specific(article: dict, ctx: dict) -> tuple:
    """Drops noise based on the specific behavior/garbage profile of individual feeds."""
    source = article.get("source", "").lower()
    text = article.get("body", "").lower()
    
    source_noise_profiles = {
        "pr newswire": ["new appointment", "product launch", "esg", "conference", "trade show"],
        "business wire": ["exhibition", "quarterly dividend", "monthly dividend"],
        "globenewswire": ["award", "recognition", "thrilled to welcome"]
    }
    
    for src, noise_keywords in source_noise_profiles.items():
        if src in source:
            for noise in noise_keywords:
                if noise in text:
                    return False, f"dropped_source_specific_noise_{noise.replace(' ', '_')}"
    return True, "passed"

# --- ONTOLOGY & RULES (PHASE 2 - MOVED UP TO MINIMIZE CPU LOAD) ---

def stage_ontology_concepts(article: dict, ctx: dict) -> tuple:
    min_score = float(ctx.get("sys_settings", {}).get("MIN_ONTOLOGY_SCORE", 0.65))
    rich_result = evaluate_ontology_rich(article.get("body", ""))
    score = rich_result.get("score", 0.0)
    article["_ontology_metadata"] = rich_result
    
    if score < min_score:
        logger.debug(f"[ONTOLOGY DROP] Score {score:.2f} < {min_score}. Snippet: {article.get('body', '')[:150]}")
        return False, f"dropped_ontology_score: {score:.2f} < {min_score}"
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
    article["_deterministic_families"] = rule_results if isinstance(rule_results, list) else []
    return True, "passed"

# --- DETERMINISTIC ENTITY STAGES (PHASE 3) ---

def stage_python_issuer_extraction(article: dict, ctx: dict) -> tuple:
    """Deterministic issuer extraction via regex header and body patterns."""
    text = article.get("body", "") + " " + article.get("headline", "")
    match = re.search(r'([A-Z][A-Za-z0-9\,\.\&\s]{2,40})\s+\((?:NYSE|NASDAQ|AMEX|OTC|TSX|LSE)\s*:\s*[A-Z]{1,5}\)', text[:1500])
    if match:
        article["_deterministic_issuer"] = match.group(1).strip()
    else:
        article["_deterministic_issuer"] = article.get("source", "UNKNOWN")
    return True, "passed"

def stage_python_ticker_lookup(article: dict, ctx: dict) -> tuple:
    """Legacy Candidate Generator"""
    version = os.environ.get("ENTITY_ENGINE_VERSION", "1")
    if version == "2":
        return stage_candidate_generator(article, ctx)
        
    text = article.get("body", "") + " " + article.get("headline", "")
    match = re.search(r'\b(?:NYSE|NASDAQ|AMEX|OTC|TSX|LSE|NYSE MKT|NYSE ARCA)\s*[:]\s*([A-Z]{1,5})\b', text, re.IGNORECASE)
    if not match:
        match = re.search(r'\((?:NYSE|NASDAQ|AMEX|OTC|TSX|LSE)\s*:\s*([A-Z]{1,5})\)', text, re.IGNORECASE)
    
    if match:
        article["_deterministic_ticker"] = match.group(1).upper()
    else:
        article["_deterministic_ticker"] = "UNKNOWN"
        
    return True, "passed"

def stage_candidate_generator(article: dict, ctx: dict) -> tuple:
    text = article.get("body", "") + " " + article.get("headline", "")
    tickers = []
    
    # Needs actual raw string literal
    matches_1 = re.findall(r'\b(?:NYSE|NASDAQ|AMEX|OTC|TSX|LSE|NYSE MKT|NYSE ARCA)\s*[:]\s*([A-Z]{1,5})\b', text, re.IGNORECASE)
    matches_2 = re.findall(r'\((?:NYSE|NASDAQ|AMEX|OTC|TSX|LSE)\s*:\s*([A-Z]{1,5})\)', text, re.IGNORECASE)
    
    candidates = []
    for t in matches_1 + matches_2:
        t = t.upper()
        if t not in tickers:
            tickers.append(t)
            candidates.append({"ticker": t, "source": "regex", "mention_frequency": text.count(t), "confidence": 1.0})
            
    article["_candidate_entities"] = candidates
    return True, "passed"

def stage_ambiguity_gate(article: dict, ctx: dict) -> tuple:
    candidates = article.get("_candidate_entities", [])
    ontology_matches = article.get("_ontology_concepts", [])
    
    has_ma_keywords = any(kw.lower() in ["merger", "acquires", "acquisition", "buyout", "takeover", "spin-off"] for kw in ontology_matches)
    
    if len(candidates) == 1 and not has_ma_keywords:
        article["_ambiguity"] = False
        article["_entities"] = [{"name": "Issuer", "ticker": candidates[0]["ticker"], "role": "issuer", "is_public": True, "extraction_confidence": 1.0, "role_confidence": 1.0}]
    else:
        article["_ambiguity"] = True
        
    return True, "passed"

def stage_entity_confidence_gate(article: dict, ctx: dict) -> tuple:
    # No longer blocking on deterministic_ticker missing
    return True, "passed"

# --- FINANCIAL CONSTRAINTS (PHASE 4) ---

def stage_financial_market_cap(article: dict, ctx: dict) -> tuple:
    return True, "passed"

def stage_tradeability_check(article: dict, ctx: dict) -> tuple:
    ticker = article.get("_target_ticker", article.get("_deterministic_ticker", "UNKNOWN"))
    if ticker == "UNKNOWN":
        return True, "passed"
        
    untradeable_suffixes = [".PK", ".OB", ".OTC", "PINK"]
    if any(suffix in ticker.upper() for suffix in untradeable_suffixes):
        return False, "dropped_untradeable_otc"
    return True, "passed"

def stage_financial_t12_floor(article: dict, ctx: dict) -> tuple:
    ticker = article.get("_target_ticker", article.get("_deterministic_ticker", "UNKNOWN"))
    if ticker != "UNKNOWN":
        metrics = get_t12_metrics(ticker)
        if not metrics.get("valid"): 
            reason = metrics.get("reason", "Unknown reason")
            return False, f"dropped_financial_t12: {reason}"
    return True, "passed"

def stage_options_chain_check(article: dict, ctx: dict) -> tuple:
    ticker = article.get("_target_ticker", article.get("_deterministic_ticker", "UNKNOWN"))
    if ticker == "UNKNOWN":
        return True, "passed"
        
    options_only = str(ctx.get("sys_settings", {}).get("Options Tradable Only", "True")).lower() == "true"
    if options_only:
        try:
            snap = query_financial_snapshot(ticker)
            if snap and snap.is_complete and not snap.options_available:
                return False, "dropped_no_options_chain"
        except Exception as e:
            pass
    return True, "passed"

def stage_liquidity_check(article: dict, ctx: dict) -> tuple:
    ticker = article.get("_target_ticker", article.get("_deterministic_ticker", "UNKNOWN"))
    if ticker == "UNKNOWN":
        return True, "passed"
    return True, "passed"

def stage_playbook_eligibility_check(article: dict, ctx: dict) -> tuple:
    """Drops the article if no active playbook exists for the detected event family."""
    active_playbooks = [str(p.get("Playbook", "")).lower() for p in ctx.get("playbooks", []) if str(p.get("Active", "TRUE")).upper() == "TRUE"]
    detected_families = [str(f.get("Rule", "")).lower() for f in article.get("_deterministic_families", []) if isinstance(f, dict)]
    
    ai_class = article.get("_ai_classification", "UNKNOWN")
    if ai_class and ai_class not in ["UNKNOWN", "ERROR", "EXHAUSTED"]:
        detected_families.append(str(ai_class).lower())
    
    if detected_families:
        has_playbook = any(family in active_playbooks for family in detected_families)
        if not has_playbook:
            return False, "dropped_no_playbook"
            
def stage_ai_ticker_resolution(article: dict, ctx: dict) -> tuple:
    version = os.environ.get("ENTITY_ENGINE_VERSION", "1")
    if version == "1":
        if article.get("_deterministic_ticker", "UNKNOWN") != "UNKNOWN":
            article["_ai_ticker"] = article.get("_deterministic_ticker")
            return True, "passed"
        ticker = extract_target_ticker(article.get("body", ""), router=ctx.get("ai_router"))
        if ticker in ["EXHAUSTED", "ERROR", "UNKNOWN"]: 
            return False, "dropped_ai_no_ticker"
        article["_ai_ticker"] = ticker
        return True, "passed"
        
    return stage_ai_entity_resolution(article, ctx)

def stage_entity_resolution(article: dict, ctx: dict) -> tuple:
    return stage_ai_entity_resolution(article, ctx)

def stage_ai_entity_resolution(article: dict, ctx: dict) -> tuple:
    if not article.get("_ambiguity", True):
        return True, "passed"
        
    parsed_entities = extract_entities_and_roles(article.get("body", ""), router=ctx.get("ai_router"))
    if parsed_entities.error:
        return False, f"dropped_entity_error: {parsed_entities.error}"
        
    article["_entities"] = [e.__dict__ for e in parsed_entities.entities]
    return True, "passed"

def stage_investment_universe_mapping(article: dict, ctx: dict) -> tuple:
    entities = article.get("_entities", [])
    for e in entities:
        if e.get("is_public") and e.get("ticker"):
            snap = None
            try:
                snap = query_financial_snapshot(e["ticker"])
            except:
                pass
            e["options_available"] = snap.options_available if snap else False
            e["tradable"] = True
    article["_entities"] = entities
    return True, "passed"

def stage_strategy_selection(article: dict, ctx: dict) -> tuple:
    entities = article.get("_entities", [])
    strategy = str(article.get("_ai_classification", "")).lower()
    
    target_ticker = None
    if "merger" in strategy or "acquisition" in strategy or "takeover" in strategy:
        target_entity = next((e for e in entities if e.get("role") == "target"), None)
        if target_entity and target_entity.get("is_public") and target_entity.get("ticker"):
            target_ticker = target_entity["ticker"]
        else:
            tradable_entities = [e for e in entities if e.get("is_public") and e.get("options_available")]
            if tradable_entities:
                tradable_entities.sort(key=lambda x: x.get("role_confidence", 0.0), reverse=True)
                target_ticker = tradable_entities[0]["ticker"]
    
    if not target_ticker:
        public_entities = [e for e in entities if e.get("is_public") and e.get("ticker")]
        if public_entities:
            public_entities.sort(key=lambda x: x.get("extraction_confidence", 0.0), reverse=True)
            target_ticker = public_entities[0]["ticker"]
            
    if target_ticker:
        article["_target_ticker"] = target_ticker
        return True, "passed"
    return False, "dropped_no_investable_entity"
    
def stage_investment_candidate_selection(article: dict, ctx: dict) -> tuple:
    return True, "passed"

def stage_ai_event_classification(article: dict, ctx: dict) -> tuple:
    ticker = article.get("_ai_ticker", "UNKNOWN")
    ai_result = classify_event(article.get("body", ""), [], ticker, router=ctx.get("ai_router"))
    
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
    score = article.get("_ai_confidence", 0.0)
    if score < min_conf:
        return False, f"dropped_ai_confidence (scored {score:.2f} < {min_conf:.2f})"
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
    "candidate_generator": stage_candidate_generator,
    "ambiguity_gate": stage_ambiguity_gate,
    "ai_entity_resolution": stage_ai_entity_resolution,
    "investment_universe_mapping": stage_investment_universe_mapping,
    "strategy_selection": stage_strategy_selection,
    "investment_candidate_selection": stage_investment_candidate_selection,
    "entity_resolution": stage_entity_resolution,
    "investment_candidate_selection": stage_investment_candidate_selection,
    "ai_event_classification": stage_ai_event_classification,
    "ai_confidence_gate": stage_ai_confidence_gate,
    "entity_confidence": stage_entity_confidence_gate,
    "playbook_gate": stage_playbook_eligibility_check,
}

def _record_screening(article: dict, telemetry: PipelineTelemetry, outcome: str, final_stage: str, drop_reason: str = None):
    """Logs every screened article (pass or drop) for operator visibility. Display-only — never affects pipeline flow."""
    company_name = article.get("_deterministic_issuer")
    if not company_name or company_name == "UNKNOWN":
        company_name = article.get("_ai_ticker") or article.get("_deterministic_ticker") or "UNKNOWN"
        
    entry = {
        "run_id": telemetry.run_id,
        "headline": article.get("headline", "Untitled"),
        "url": article.get("url", "UNKNOWN"),
        "source": article.get("source", "UNKNOWN"),
        "outcome": outcome,
        "final_stage": final_stage,
        "drop_reason": drop_reason,
        "ticker": company_name,
        "company_name": company_name,
        "event_family": article.get("_ai_classification"),
        "ingestion_mode": article.get("_ingestion_mode", "UNKNOWN"),
        "body_snippet": article.get("body", "")[:3000]
    }
    logger.info(f"[SCREENED] '{entry['headline'][:80]}' -> {outcome} @ {final_stage}" + (f" ({drop_reason})" if drop_reason else ""))
    try:
        log_article_screening(entry)
    except Exception as e:
        logger.error(f"[SCREENING LOG FAULT] {e}")

def process_article(article: dict, telemetry: PipelineTelemetry, config_manifest: dict, manifest_hash: str, ai_router=None):
    ctx = {
        "sys_settings": config_manifest.get("settings", [])[0] if config_manifest.get("settings") else {},
        "semantic_concepts": config_manifest.get("semantic_concepts", []),
        "event_statuses": config_manifest.get("event_statuses", []),
        "rules": config_manifest.get("rules", []),
        "global_exclusions": config_manifest.get("global_exclusions", []),
        "document_type_scores": config_manifest.get("document_type_scores", []),
        "playbooks": config_manifest.get("playbooks", []),
        "financial_rules": config_manifest.get("financial_rules", []),
        "ai_router": ai_router
    }
    
    raw_pipeline_sheet = config_manifest.get("pipeline", [])
    if raw_pipeline_sheet:
        sorted_stages = sorted([s for s in raw_pipeline_sheet if str(s.get("Active", "TRUE")).upper() == "TRUE"], key=lambda x: int(x.get("Order", 99)))
        execution_order = [s.get("Stage_ID") for s in sorted_stages]
        validate_pipeline_dag(execution_order)
    else:
        version = os.environ.get("ENTITY_ENGINE_VERSION", "1")
        if version == "1":
            execution_order = [
                "dedupe_hash", "dedupe_issuer_memory", "exclude_global_keywords", 
                "exclude_issuer_feed", "exclude_source_specific", "ontology_concepts", 
                "ontology_status", "document_scoring", "regex_rules", 
                "python_issuer_extraction", "python_ticker_lookup", "ai_ticker_resolution",
                "entity_confidence_gate", "financial_market_cap", "tradeability_check", 
                "financial_t12_floor", "options_chain_check", "liquidity_check", 
                "ai_event_classification", "ai_confidence_gate", "playbook_eligibility_check"
            ]
        else:
            execution_order = [
                "dedupe_hash", "dedupe_issuer_memory", "exclude_global_keywords", 
                "exclude_issuer_feed", "exclude_source_specific", "ontology_concepts", 
                "ontology_status", "document_scoring", "regex_rules", 
                "python_issuer_extraction", "candidate_generator", "ambiguity_gate", 
                "ai_entity_resolution", "ai_event_classification", "ai_confidence_gate", 
                "investment_universe_mapping", "strategy_selection", "investment_candidate_selection",
                "entity_confidence_gate", "financial_market_cap", "tradeability_check", 
                "financial_t12_floor", "options_chain_check", "liquidity_check", 
                "playbook_eligibility_check"
            ]

    # Validate DAG instead of silently overriding
    validate_pipeline_dag(execution_order)

    # Enforce correct topological ordering for Playbook Gate (Legacy only if V1)
    pb_gates = [g for g in ["playbook_gate", "playbook_eligibility_check"] if g in execution_order]
    if "ai_event_classification" in execution_order and pb_gates:
        ai_idx = execution_order.index("ai_event_classification")
        for pg in pb_gates:
            pg_idx = execution_order.index(pg)
            if pg_idx < ai_idx:
                execution_order.remove(pg)
                ai_idx = execution_order.index("ai_event_classification") # recount after remove
                insert_idx = ai_idx + 1
                if "ai_confidence_gate" in execution_order:
                    insert_idx = max(insert_idx, execution_order.index("ai_confidence_gate") + 1)
                execution_order.insert(insert_idx, pg)

    stage_timings = {}

    for stage_name in execution_order:
        stage_func = STAGE_REGISTRY.get(stage_name.lower())
        if not stage_func: 
            logger.warning(f"Configuration requested unknown pipeline stage: {stage_name}")
            continue
            
        start_cpu = time.perf_counter_ns()
        start_net = article.get("_net_time_accumulator", 0)
        start_api = article.get("_api_call_accumulator", 0)

        passed, drop_reason = stage_func(article, ctx)
        
        delta_cpu = time.perf_counter_ns() - start_cpu
        delta_net = article.get("_net_time_accumulator", start_net) - start_net
        delta_api = article.get("_api_call_accumulator", start_api) - start_api
        
        stage_timings[stage_name] = round(delta_cpu / 1_000_000, 3)

        telemetry.track_stage_performance(
            stage=stage_name,
            outcome="passed" if passed else "rejected",
            cpu_ns=delta_cpu,
            network_ns=delta_net,
            api_calls=delta_api,
            reason=drop_reason if not passed else "N/A"
        )

        if not passed:
            telemetry.track(drop_reason)
            _record_screening(article, telemetry, outcome="DROPPED", final_stage=stage_name, drop_reason=drop_reason)
            
            if stage_name != "dedupe_hash":
                evt_id = article.get("_internal_event_id", "UNKNOWN")
                dec_hash = hashlib.md5(f"{evt_id}:{time.time()}".encode()).hexdigest()[:12].upper()
                decision_capsule = {
                    "decision_id": f"DEC-{dec_hash}",
                    "event_id": evt_id,
                    "manifest_hash": manifest_hash,
                    "runtime_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT"),
                    "detection_outcome": "DROPPED",
                    "terminal_stage": stage_name,
                    "headline": article.get("headline", "Corporate Announcement"),
                    "url": article.get("url", "UNKNOWN"),
                    "ontology_metadata": article.get("_ontology_metadata", {}),
                    "execution_timings": stage_timings
                }
                commit_decision_capsule(decision_capsule)
            return False
            
    telemetry.track("alerts_generated")
    mode = article.get("_ingestion_mode")
    if mode == "RSS": telemetry.track("RSS_alerts")
    elif mode == "HTML": telemetry.track("HTML_alerts")
    
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
        },
        "ontology_metadata": article.get("_ontology_metadata", {}),
        "execution_timings": stage_timings
    }
    
    commit_decision_capsule(decision_capsule)
    logger.info(f"[ALERT GENERATED] {ticker} - {event_family}")
    _record_screening(article, telemetry, outcome="PASSED", final_stage="AI_APPROVED")
    
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


def validate_pipeline_dag(execution_order: list):
    version = os.environ.get("ENTITY_ENGINE_VERSION", "1")
    if version == "1":
        return
        
    required_order = [
        ("candidate_generator", "ambiguity_gate"),
        ("ai_event_classification", "strategy_selection")
    ]
    
    for first, second in required_order:
        if first in execution_order and second in execution_order:
            if execution_order.index(first) > execution_order.index(second):
                err = f"CRITICAL: Invalid Pipeline DAG. {first} MUST PRECEDE {second}."
                try:
                    from src.alerts.email import send_alert
                    send_alert({"headline": err, "drop_reason": "DAG Error", "decision_id": "SYS", "final_stage": "DAG_VALIDATION", "pipeline_metrics": {}}, force_email=True)
                except:
                    pass
                raise ValueError(err)

def validate_pipeline_dag(execution_order: list):
    version = os.environ.get("ENTITY_ENGINE_VERSION", "1")
    if version == "1":
        return
        
    required_order = [
        ("candidate_generator", "ambiguity_gate"),
        ("ai_event_classification", "strategy_selection")
    ]
    
    for first, second in required_order:
        if first in execution_order and second in execution_order:
            if execution_order.index(first) > execution_order.index(second):
                err = f"CRITICAL: Invalid Pipeline DAG. {first} MUST PRECEDE {second}."
                try:
                    send_alert({
                        "manifest_registry": {"decision_id": "SYS"},
                        "detection_vector": {"target_ticker": "DAG_ERROR", "detected_event_type": "Pipeline Error"},
                        "headline": err,
                        "research_summary": "Execution Halted due to DAG violation."
                    })
                except Exception as e:
                    logger.error(f"Failed to send DAG alert: {e}")
                raise ValueError(err)

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
        
        ai_router = ProviderRouter()
        ai_router.update_config(config_manifest.get("settings", {}))
    except Exception as e:
        logger.critical(f"Failed to fetch Configuration Manifest: {e}")
        sys.exit(1)
    
    try:
        raw_articles, ingestion_ledger = fetch_all_feeds(config_manifest.get("sources", [])) 
        telemetry.metrics["downloaded"] = len(raw_articles)
        telemetry.metrics["RSS_downloaded"] = sum(1 for a in raw_articles if a.get("_ingestion_mode") == "RSS")
        telemetry.metrics["HTML_downloaded"] = sum(1 for a in raw_articles if a.get("_ingestion_mode") == "HTML")
        
        # Immediate Global Deduplication
        unique_articles = []
        seen_hashes = set()
        
        ledger_unique = {f"{entry['source']}::{entry['channel']}": 0 for entry in ingestion_ledger}
        
        for article in raw_articles:
            title = article.get("headline", "").strip().lower()
            source = article.get("source", "").strip().lower()
            if not title or title == "no title" or title == "html document":
                title = article.get("body", "")[:200].strip().lower()
                
            dup_hash = hashlib.md5(f"{source}::{title}".encode('utf-8')).hexdigest()
            
            if dup_hash not in seen_hashes:
                seen_hashes.add(dup_hash)
                unique_articles.append(article)
                
                k = f"{article.get('source')}::{article.get('_ingestion_mode')}"
                if k in ledger_unique:
                    ledger_unique[k] += 1
            else:
                logger.debug(f"[DEDUPE] Dropped overlapping article: {article.get('headline')} from {article.get('source')} ({article.get('_ingestion_mode')})")
                
        for entry in ingestion_ledger:
            k = f"{entry['source']}::{entry['channel']}"
            entry["unique_found"] = ledger_unique.get(k, 0)
            
        telemetry.ingestion_ledger = ingestion_ledger
        
        telemetry.metrics["RSS_unique"] = sum(1 for a in unique_articles if a.get("_ingestion_mode") == "RSS")
        telemetry.metrics["HTML_unique"] = sum(1 for a in unique_articles if a.get("_ingestion_mode") == "HTML")
        telemetry.metrics["unique_articles"] = len(unique_articles)
        
        logger.info(f"Global deduplication complete: {len(raw_articles)} raw -> {len(unique_articles)} unique.")

        for article in unique_articles:
            try:
                process_article(article, telemetry, config_manifest, manifest_hash, ai_router)
            except Exception as e:
                logger.error(f"Error processing article: {e}")
                telemetry.track("errors")
    except Exception as e:
        logger.critical(f"Fatal error in main pipeline loop: {e}")
    
    finally:
        logger.info("Pipeline execution finished. Generating observability exports...")
        
        logger.info("\n=== 📉 PIPELINE ECONOMICS & STAGE FUNNEL 📉 ===")
        for stage, data in telemetry.stage_analytics.items():
            logger.info(f"[{stage.upper()}] Entered: {data['entered']} | Passed: {data['passed']} | Rejected: {data['rejected']} | CPU: {data['cpu_ms']}ms | Net: {data['network_ms']}ms | API: {data['api_calls']}")
            if data['drop_reasons']:
                logger.info(f"    Drop Reasons: {data['drop_reasons']}")
        logger.info("===============================================\n")
        
        try:
            git_commit = subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode('ascii').strip()
            git_branch = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).decode('ascii').strip()
        except:
            git_commit = "unknown"
            git_branch = "unknown"
            
        health_payload = {
            "run_id": telemetry.run_id,
            "total_scanned": telemetry.metrics.get("downloaded", 0),
            "articles": telemetry.metrics.get("alerts_generated", 0),
            "errors": telemetry.metrics.get("errors", 0) + telemetry.metrics.get("ai_exhausted", 0),
            "runtime": telemetry.get_runtime(),
            "git_commit": git_commit,
            "branch": git_branch,
            "daily": {
                "run_id": telemetry.run_id,
                "downloaded": telemetry.metrics.get("downloaded", 0),
                "RSS_downloaded": telemetry.metrics.get("RSS_downloaded", 0),
                "HTML_downloaded": telemetry.metrics.get("HTML_downloaded", 0),
                "RSS_unique": telemetry.metrics.get("RSS_unique", 0),
                "HTML_unique": telemetry.metrics.get("HTML_unique", 0),
                "RSS_alerts": telemetry.metrics.get("RSS_alerts", 0),
                "HTML_alerts": telemetry.metrics.get("HTML_alerts", 0),
                "unique_articles": telemetry.metrics.get("unique_articles", 0),
                "health_score": 100.0,
                "funnel": telemetry.stage_analytics
            },
            "funnel": telemetry.stage_analytics,
            "ingestion_ledger": getattr(telemetry, "ingestion_ledger", [])
        }
        save_workflow_health(health_payload)
        
        # --- V4 Audit Logging & Events ---
        try:
            log_audit_source_metrics(telemetry.run_id, health_payload.get("ingestion_ledger", []))
            
            # Log scraper events
            has_emergency_stop = False
            for entry in health_payload.get("ingestion_ledger", []):
                meta = entry.get("metadata", {})
                if meta.get("emergency_stop"):
                    has_emergency_stop = True
                    log_audit_event(telemetry.run_id, entry.get("source"), "EMERGENCY_LIMIT_REACHED", "CRITICAL", f"Reason: {meta.get('reason')}")
                elif entry.get("status") in ["TIMEOUT", "ERROR"]:
                    log_audit_event(telemetry.run_id, entry.get("source"), entry.get("status"), "WARN", entry.get("error_message"))

            if 'ai_router' in locals() and hasattr(ai_router, 'get_telemetry'):
                log_audit_ai_metrics(telemetry.run_id, ai_router.get_telemetry())
                # Log AI router events
                for evt in ai_router.get_events():
                    log_audit_event(telemetry.run_id, evt.get("source_or_provider"), evt.get("event_type"), evt.get("severity"), evt.get("details"))
                    
            # Check for catastrophic failures
            if has_emergency_stop:
                from src.alerts.email import send_alert
                send_alert({
                    "headline": "CRITICAL HEALTH ALERT",
                    "url": "https://github.com/tonyfonda-eng/SSR",
                    "research_summary": "Emergency stop was reached. Immediate investigation required.",
                    "is_update": False,
                    "manifest_registry": {"decision_id": telemetry.run_id},
                    "detection_vector": {"detected_event_type": "SYSTEM FAILURE", "target_ticker": "SSR_OPS"},
                    "syndication_lineage": {"canonical_sensor_id": "Flight Recorder"}
                })
                    
        except Exception as e:
            logger.error(f"[AUDIT] Failed to save V4 audit metrics/events: {e}")
            
        try:
            import os
            ledger_path = "docs/ingestion_ledger.json"
            history = []
            if os.path.exists(ledger_path):
                with open(ledger_path, "r") as f:
                    try:
                        history = json.load(f)
                    except:
                        pass
            for entry in health_payload["ingestion_ledger"]:
                entry["run_id"] = telemetry.run_id
                entry["timestamp"] = datetime.now(timezone.utc).isoformat()
            history = health_payload["ingestion_ledger"] + history
            history = history[:1000]
            os.makedirs(os.path.dirname(ledger_path), exist_ok=True)
            with open(ledger_path, "w") as f:
                json.dump(history, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save ingestion ledger history: {e}")
            
        try:
            logger.info("Dumping Ledger to archive_data.json...")
            export_archive_json("docs/archive_data.json")
            
            logger.info("Exporting article screening log...")
            if callable(export_screening_log):
                export_screening_log("docs/screening_log.json")
            else:
                export_screening_json("docs/screening_log.json")
                
            logger.info("Exporting real-time source audit...")
            export_realtime_audit("docs/realtime_audit.json")

            logger.info("Rebuilding ALL HTML Dashboards...")
            generate_dashboard_html([], "docs/index.html", health_payload)
            generate_pipeline_health_html("docs/pipeline_health.html", health_payload)
            generate_decision_analytics_html("docs/decision_analytics.html", health_payload)
            generate_screening_log_html("docs/archive.html")
            logger.info("[SUCCESS] All institutional HTML dashboards rebuilt in docs/")
        except Exception as e:
            logger.error(f"Frontend Data & HTML Export failed: {e}")

if __name__ == "__main__":
    main()