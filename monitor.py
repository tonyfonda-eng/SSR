import re
import time
import datetime
import os
import sys
import requests
import traceback
import feedparser
import yfinance as yf
from collections import defaultdict
import json
import uuid
import hashlib

# --- WAF BYPASS & GLOBAL HTTP SHIELD ---
_orig_get = requests.get

def _spoofed_get(*args, **kwargs):
    headers = kwargs.get('headers', {})
    if isinstance(headers, dict) and 'User-Agent' not in headers:
        headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    kwargs['headers'] = headers
    
    if 'timeout' not in kwargs:
        kwargs['timeout'] = (3.0, 15.0)
        
    return _orig_get(*args, **kwargs)

requests.get = _spoofed_get
# ---------------------------------------

from src.config.settings import SHEET_URL

from src.database import (
    initialise_database, get_or_create_event, log_sensor_lineage,
    commit_decision_capsule, register_configuration_manifest,
    save_workflow_health, save_exception_log, save_ai_usage,
    save_source_stats, get_dashboard_state, set_dashboard_state,
    get_recent_lifecycle_logs, export_archive_json, get_30_day_average,
    get_30_day_source_averages, perform_housekeeping, get_pending_reminders,
    mark_reminder_sent, save_reminder, log_research, track_company, create_event_if_new,
    get_latest_config_snapshot, save_config_snapshot
)

from src.scrapers.prnewswire import download_article
from src.scrapers import get_scraper_for_source
from src.sheets import (
    load_rules, load_sources, load_playbooks, append_to_research_queue,
    update_last_checked, load_global_exclusions, load_gold_standards,
    log_unknown_event, load_daily_memory, batch_append_daily_memory, 
    prune_daily_memory, load_source_reliability, load_document_type_scores,
    aggregate_and_sync_yesterday, get_system_settings
)
from src.rules_engine import evaluate
from src.ai import classify_event, execute_playbook, extract_target_ticker, extract_halt_date
from src.alerts.email import send_alert
from src.issuer import extract_issuing_company
from src.drift_monitor import check_pipeline_drift
from src.ontology import extract_concepts, extract_statuses, load_ontology
from src.financials import get_t12_metrics
from src.monitoring import MetricsCollector
from src.html_generator import generate_dashboard_html, generate_archive_html, generate_decision_analytics_html


class EvidenceCapsule:
    """
    SSR 2.0 Core Paradigm: The Immutable Evidence Capsule.
    """
    def __init__(self, event_id: str, article_id: str, manifest_hash: str, raw_text: str):
        self.decision_id = f"DSC-{uuid.uuid4()}"
        self.event_id = event_id
        self.article_id = article_id
        self.manifest_hash = manifest_hash
        self.raw_text = raw_text
        self.timings = {"ingest_repo_ms": 0, "transformation_ms": 0, "ontology_ms": 0, "rules_ms": 0, "ai_inference_ms": 0, "financial_query_ms": 0}
        self.evidence = {"SUPPORTING": [], "OPPOSING": []}
        self.outcome = "PENDING"
        self.terminal_stage = "None"
        self.completeness_score = 1.0
        self.ai_data = {}
        self.ticker = "UNKNOWN"
        self.event_family = "Unknown"
        self.rule_threshold = 10
        self.market_data_snapshot = None # Phase 1: Store specific financial facts used
        self.last_timer = time.perf_counter_ns()

    def append_evidence(self, direction: str, stage: str, component: str, assertion: str, weight: float, offsets=None):
        ev = {
            "evidence_id": f"EVID-{uuid.uuid4()}",
            "stage": stage,
            "evidence_direction": direction.upper(),
            "source_component": component,
            "assertion_key": assertion,
            "confidence_weight": weight
        }
        if offsets:
            ev.update(offsets)
        self.evidence[direction.upper()].append(ev)

    def mark_timing(self, stage_key: str):
        now = time.perf_counter_ns()
        self.timings[stage_key] = (now - self.last_timer) // 1_000_000
        self.last_timer = now

    def compile_manifest(self) -> dict:
        return {
            "manifest_registry": {
                "decision_id": self.decision_id,
                "event_id": self.event_id,
                "article_id": self.article_id,
                "configuration_manifest_hash": self.manifest_hash,
                "execution_timestamp_gmt": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT"),
                "evidence_completeness_score": self.completeness_score
            },
            "detection_vector": {
                "outcome": self.outcome,
                "terminal_stage": self.terminal_stage,
                "detected_event_type": self.event_family,
                "target_ticker": self.ticker,
                "rule_threshold_used": self.rule_threshold
            },
            "performance_telemetry_ms": self.timings,
            "evidentiary_provenance_dag": {
                "supporting_evidence": self.evidence["SUPPORTING"],
                "opposing_evidence": self.evidence["OPPOSING"]
            },
            "market_data_snapshot": self.market_data_snapshot
        }


class IssuerMemory:
    def __init__(self):
        self.issuers = set()
        self._new_additions = list()

    def load_from_db(self):
        issuers = load_daily_memory(SHEET_URL)
        self.issuers = set([str(k).lower() for k in issuers if k])

    def is_duplicate(self, issuer):
        if not issuer or issuer == "UNKNOWN": return False
        return issuer.lower() in self.issuers

    def add(self, issuer):
        if issuer and issuer != "UNKNOWN":
            key_lower = issuer.lower()
            if key_lower not in self.issuers:
                self.issuers.add(key_lower)
                self._new_additions.append(issuer)

    def flush_to_sheets(self):
        if self._new_additions:
            try:
                batch_append_daily_memory(SHEET_URL, self._new_additions)
                self._new_additions.clear()
            except Exception as e:
                print(f" [WARNING] Failed to flush daily memory: {e}")

    @property
    def size(self):
        return len(self.issuers)


def compute_config_diff(old_json_str, new_json_str):
    """Calculates granular deltas between Google Sheet config snapshots."""
    old_c = json.loads(old_json_str) if old_json_str else {}
    new_c = json.loads(new_json_str) if new_json_str else {}
    diffs = []
    for k in ["rules", "sources", "playbooks", "global_exclusions", "gold_standards"]:
        old_len = len(old_c.get(k, []))
        new_len = len(new_c.get(k, []))
        if old_len != new_len:
            diffs.append(f"- {k.capitalize()} modified: was {old_len} items, now {new_len} items.")
    if not diffs:
        return "- Internal configuration thresholds or content parameters modified."
    return "\n".join(diffs)


def evaluate_capsule(capsule: EvidenceCapsule, primary: dict, rules, playbook_map, global_exclusions, gold_standards,
                     issuer_memory, document_type_scores, ontology_stats, source_reliability_scores, 
                     research_queue_rows, financials_cache):
    
    metrics = MetricsCollector.get_instance()
    
    source_name = primary["source_name"]
    url = primary["url"]
    title = primary["title"]
    body = primary["body"]
    triage_all = primary.get("triage_all", False)
    document_type = primary.get("document_type")
    
    # Phase 2: Externalize hardcoded decision constants
    rule_threshold = int(metrics.settings.get("RULE_THRESHOLD", 10))
    capsule.rule_threshold = rule_threshold
    
    material_keywords = metrics.settings.get("MATERIAL_KEYWORDS", [
        "bump", "increase", "amend", "terminate", "cancel", 
        "regulatory approval", "revised", "superior proposal", 
        "competing", "blocked"
    ])
    if isinstance(material_keywords, str):
        material_keywords = [k.strip() for k in material_keywords.split(",")]
    
    metrics.track_funnel("downloaded", 1)

    def flush_termination(outcome, terminal_stage):
        capsule.outcome = outcome
        capsule.terminal_stage = terminal_stage
        manifest_json = capsule.compile_manifest()
        
        db_payload = {
            "decision_id": capsule.decision_id,
            "event_id": capsule.event_id,
            "manifest_hash": capsule.manifest_hash,
            "detection_outcome": outcome,
            "terminal_stage": terminal_stage,
            "evidence_completeness_score": capsule.completeness_score,
            "evidence_provenance_ledger": manifest_json["evidentiary_provenance_dag"]["supporting_evidence"] + manifest_json["evidentiary_provenance_dag"]["opposing_evidence"],
            "ai_core_inference": capsule.ai_data,
            "performance_telemetry_ms": capsule.timings,
            "market_data_snapshot": capsule.market_data_snapshot
        }
        commit_decision_capsule(db_payload, manifest_json)
        return 1 if outcome == "DETECTED" else 0

    if not body:
        metrics.track_funnel("empty_body")
        capsule.append_evidence("OPPOSING", "Ingestion", "Body Extractor", "Empty Body String", 1.0)
        return flush_termination("DROPPED", "Ingestion")

    capsule.mark_timing("ingest_repo_ms")

    # --- Issuer Resolution Phase ---
    issuer = extract_issuing_company(source_name, title, body)
    if issuer == "EXHAUSTED":
        capsule.append_evidence("OPPOSING", "Issuer Extraction", "AI Limits", "API Providers Exhausted", 1.0)
        return flush_termination("DROPPED", "Issuer Extraction")

    if issuer_memory and issuer_memory.is_duplicate(issuer):
        metrics.track_funnel("duplicate_issuer")
        capsule.append_evidence("OPPOSING", "Daily Memory", "Issuer Cache", f"Duplicate Issuer: {issuer}", 1.0)
        return flush_termination("DROPPED", "Daily Memory")

    # --- Global Exclusions Phase ---
    title_lower = title.lower()
    body_lower = body.lower()
    for ex in (global_exclusions or []):
        ex_lower = str(ex).lower()
        if re.search(r'\b' + re.escape(ex_lower) + r'\b', title_lower) or re.search(r'\b' + re.escape(ex_lower) + r'\b', body_lower):
            metrics.track_funnel("global_exclusion")
            capsule.append_evidence("OPPOSING", "Global Exclusions", "Regex Filter", f"Matched Exclusion: '{ex}'", 1.0)
            return flush_termination("DROPPED", "Global Exclusions")

    print(f" -> Processing: {title}")
    raw_text = f"{title}\n\n{body}"
    capsule.mark_timing("transformation_ms")

    # --- Ontology Phase ---
    ontology_concepts = []
    ontology_statuses = []
    try:
        ontology_concepts = extract_concepts(raw_text)
        ontology_statuses = extract_statuses(raw_text)
    except Exception as e:
        capsule.append_evidence("OPPOSING", "Ontology", "NLP Engine", f"Extraction Error: {e}", 1.0)

    if ontology_concepts:
        for cid, conf in ontology_concepts:
            capsule.append_evidence("SUPPORTING", "Ontology", "Ontology Dictionary v2.0", f"Matched Concept: {cid}", float(conf) / 100.0 if conf else 1.0)
    capsule.mark_timing("ontology_ms")

    # --- Deterministic Rules Phase ---
    source_rel = source_reliability_scores.get(source_name, 0) if source_reliability_scores else 0
    article_obj = {"raw_text": raw_text, "document_type": document_type}
    
    matches = evaluate(article_obj, rules, document_type_scores if document_type_scores else [], 
                       ontology_concepts=ontology_concepts, ontology_statuses=ontology_statuses, 
                       source_reliability=source_rel, threshold=rule_threshold)
    capsule.mark_timing("rules_ms")
    
    if not matches:
        metrics.track_funnel("rules_rejected")
        capsule.append_evidence("OPPOSING", "Rules Engine", "Deterministic Evaluator", f"Failed Rules Threshold (<{rule_threshold})", 1.0)
        return flush_termination("DROPPED", "Rules Engine")
    
    capsule.append_evidence("SUPPORTING", "Rules Engine", "Deterministic Evaluator", f"Passed threshold ({rule_threshold}) with Score: {matches[0].get('Score', rule_threshold)}", 1.0)

    # --- AI Inference Phase ---
    metrics.track_funnel("reached_ai")
    
    ticker = extract_target_ticker(body)
    capsule.ticker = ticker
    
    if "MOCK AI" in ticker or "ERROR" in ticker or ticker == "EXHAUSTED":
        metrics.track_funnel("ai_exhausted")
        capsule.append_evidence("OPPOSING", "AI Core", "Ticker Extraction", "AI Providers Exhausted/Error", 1.0)
        return flush_termination("DROPPED", "AI Core")
        
    if ticker == "PRIVATE":
        metrics.track_funnel("ai_rejected_private")
        capsule.append_evidence("OPPOSING", "AI Core", "Entity Resolution", "Target is a Private Company", 0.99)
        return flush_termination("DROPPED", "AI Core")

    # --- Financial Verification Phase ---
    options_available = False
    market_cap = None
    market_data_str = ""
    ticker_info = None 
    options = []
    
    if ticker != "UNKNOWN" and "MOCK AI" not in ticker:
        if financials_cache is not None and ticker in financials_cache:
            ticker_info = financials_cache[ticker].get("info")
            options = financials_cache[ticker].get("options")
            options_available = financials_cache[ticker].get("options_available", False)
        else:
            try:
                time.sleep(0.5)
                yf_ticker = yf.Ticker(ticker)
                ticker_info = yf_ticker.info
                options = yf_ticker.options
                options_available = len(options) > 0 if options else False
                if financials_cache is not None:
                    financials_cache[ticker] = {"info": ticker_info, "options": options, "options_available": options_available}
            except Exception as e:
                capsule.completeness_score = 0.86
                capsule.append_evidence("OPPOSING", "Financials", "Yahoo API", f"Financial Data Missing: {e}", 0.5)
                ticker_info, options = None, []

        if ticker_info:
            market_cap = ticker_info.get('marketCap')
            current_price = ticker_info.get('currentPrice', ticker_info.get('regularMarketPrice'))
            total_cash = ticker_info.get('totalCash')
            total_debt = ticker_info.get('totalDebt')
            
            # TASK 1.2: Snapshot Market Data dynamically used per decision
            capsule.market_data_snapshot = json.dumps({
                "market_cap": market_cap,
                "current_price": current_price,
                "options_available": options_available,
                "total_cash": total_cash,
                "total_debt": total_debt
            })

            if market_cap:
                market_data_str += f"Current Market Cap: ${market_cap:,.2f}\n"
            if current_price:
                market_data_str += f"Current Share Price: ${current_price}\n\n"
                
        if options_available:
            market_data_str += "Exchange-listed Options Available: YES\n"
        else:
            market_data_str += "Exchange-listed Options Available: NO\n"
            
    capsule.mark_timing("financial_query_ms")

    # --- AI Strategy Playbook Phase ---
    event_family = classify_event(body, matches, ticker=ticker, market_cap=market_cap)
    capsule.event_family = event_family
    capsule.mark_timing("ai_inference_ms")
    
    capsule.ai_data = {
        "raw_provider_json": "{}", 
        "parsed_structural_properties": {"ticker": ticker, "strategy": event_family},
        "semantic_interpretation": event_family,
        "aggregate_confidence": matches[0].get("Score", 50) / 100.0
    }
    
    if event_family == "EXHAUSTED":
        metrics.track_funnel("ai_exhausted")
        capsule.append_evidence("OPPOSING", "AI Classification", "Strategy Evaluator", "AI Providers Exhausted", 1.0)
        return flush_termination("DROPPED", "AI Classification")
        
    if "false positive" in event_family.lower():
        metrics.track_funnel("ai_rejected_false_positive")
        capsule.append_evidence("OPPOSING", "AI Classification", "Strategy Evaluator", "AI Assessed False Positive", 0.95)
        if not triage_all:
            return flush_termination("DROPPED", "AI Classification")

    if event_family.strip().lower() == "unknown":
        capsule.append_evidence("SUPPORTING", "AI Classification", "Strategy Evaluator", "Unknown Event Family", 0.5)
        log_unknown_event(sheet_url=SHEET_URL, Source=source_name, article_title=title, article_url=url, 
                          rules_score=matches[0].get("Score", 0), ai_response=event_family)
        return flush_termination("ARCHIVED", "AI Classification")

    if event_family == "M&A Naked Call Strategy" and not options_available:
        metrics.track_funnel("playbook_rejected")
        capsule.append_evidence("OPPOSING", "Financial Verification", "Options Check", "No Tradable Options Found", 1.0)
        return flush_termination("DROPPED", "Financial Verification")

    if event_family == "Resumption of Trading":
        halt_date_str = extract_halt_date(body)
        pre_halt = ticker_info.get('previousClose') if ticker_info else None
        t12_data = get_t12_metrics(ticker, pre_halt_price=pre_halt, halt_date_str=halt_date_str)
        if not t12_data.get('valid'):
            metrics.track_funnel("playbook_rejected")
            capsule.append_evidence("OPPOSING", "Financial Verification", "T12 Structural Floor", f"Floor failed: {t12_data.get('reason')}", 1.0)
            return flush_termination("DROPPED", "Financial Verification")
            
        capsule.append_evidence("SUPPORTING", "Financial Verification", "T12 Engine", f"Net Cash/Share: ${t12_data.get('net_cash_per_share', 0):.2f}", 1.0)
        market_data_str += f"Net Cash Per Share: ${t12_data.get('net_cash_per_share', 0):.2f}\n"

    # --- Action / Dispatch Phase ---
    is_update = False
    if ticker != "UNKNOWN" and "MOCK AI" not in ticker:
        track_company(ticker)
        event_id, is_new = create_event_if_new(event_family, ticker)
        
        if not is_new:
            is_material = any(kw in body_lower or kw in title_lower for kw in material_keywords)
            
            if is_material:
                is_update = True
                capsule.append_evidence("SUPPORTING", "Deduplication", "Material Engine", "Material Update Keyword Found", 0.9)
            else:
                metrics.track_funnel("duplicate_event")
                capsule.append_evidence("OPPOSING", "Deduplication", "Material Engine", "No Material Update Justified", 1.0)
                return flush_termination("DROPPED", "Deduplication")
    else:
        event_id = f"UNKNOWN_{capsule.event_id}"

    confidence = matches[0].get("Score", 50)
    playbook_steps = playbook_map.get(event_family, "")
    if event_family == "Resumption of Trading":
        playbook_steps += "\nCRITICAL T12 INSTRUCTIONS: Why did the halt occur? How long did it last?"
        
    gold_standard = gold_standards.get(event_family) if gold_standards else None
    
    print(f" [AI RESEARCH] Generating Investment Memo...")
    research_summary = execute_playbook(body, playbook_steps, event_family, gold_standard, market_data_str=market_data_str)
    
    log_research(event_id, capsule.event_id, confidence, research_summary)
    
    queue_payload = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT"),
        "ticker": ticker,
        "issuer": issuer,
        "event_family": event_family,
        "url": url,
        "status": "Pending"
    }
    
    if research_queue_rows is not None:
        research_queue_rows.append(queue_payload)
    else:
        append_to_research_queue(sheet_url=SHEET_URL, data_row=queue_payload)
    
    try:
        # Pass the manifest dictionary forward if your email dispatcher uses it.
        # Ensure compatibility with alerts.email
        send_alert(
            article_title=title,
            article_url=url,
            event_family=event_family,
            confidence=confidence,
            research_summary=research_summary,
            evidence_log=matches[0].get("Evidence", []),
            is_update=is_update
        )
        metrics.track_funnel("alerts_sent")
        capsule.append_evidence("SUPPORTING", "Dispatch", "Email Handler", "Alert Sent Successfully", 1.0)
    except Exception as e:
        capsule.append_evidence("OPPOSING", "Dispatch", "Email Handler", f"Send Failed: {e}", 1.0)
        
    go_shop_match = re.search(r'GO-SHOP EXPIRY:\s*(\d{4}-\d{2}-\d{2})', research_summary)
    if go_shop_match:
        expiry_date = go_shop_match.group(1)
        save_reminder(event_id, ticker, expiry_date, f"Go-Shop period for {ticker} expires TODAY ({expiry_date}).")
        
    if issuer_memory and issuer != "UNKNOWN":
        issuer_memory.add(issuer)
        
    return flush_termination("DETECTED", "Complete")


def process_1_feed(rss_url, source_name, triage_all=False, country=None, language=None):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(rss_url, headers=headers) 
        response.raise_for_status()
        feed = feedparser.parse(response.content)
    except Exception as e:
        return [], 0
        
    parsed_articles = []
    for entry in feed.entries:
        article_id = entry.link.rstrip("/").split("/")[-1].replace(".html", "")
        body = getattr(entry, "summary", getattr(entry, "description", ""))
        published = getattr(entry, "published", "")
        parsed_articles.append({
            "source_name": source_name,
            "article_id": article_id,
            "title": entry.title,
            "url": entry.link,
            "published": published,
            "body": body,
            "triage_all": triage_all,
            "document_type": None,
            "country": country,
            "language": language
        })
        
    feed_len = len(feed.entries)
    del feed 
    return parsed_articles, feed_len


def process_custom_scraper(scraper, source_name, rss_url=None, triage_all=False, country=None, language=None):
    try:
        articles = scraper.get_latest_articles(rss_url=rss_url)
    except Exception as e:
        return [], 0
        
    parsed_articles = []
    for i, article in enumerate(articles):
        body = article.get("body", "")
        parsed_articles.append({
            "source_name": source_name,
            "article_id": article['id'],
            "title": article['title'],
            "url": article['url'],
            "published": article.get('published', ''),
            "body": body,
            "triage_all": triage_all,
            "document_type": article.get("document_type"),
            "country": country,
            "language": language
        })
        
    return parsed_articles, len(articles)


def cluster_articles(articles):
    clusters = []
    for article in articles:
        if not article.get('body'):
            continue
            
        found_cluster = False
        art_tokens = set(article['title'].lower().split())
        
        for cluster in clusters:
            rep = cluster[0]
            rep_tokens = set(rep['title'].lower().split())
            
            if not art_tokens or not rep_tokens:
                continue
                
            overlap = len(art_tokens.intersection(rep_tokens))
            similarity = overlap / float(min(len(art_tokens), len(rep_tokens)))
            
            if similarity > 0.75:  
                cluster.append(article)
                found_cluster = True
                break
                
        if not found_cluster:
            clusters.append([article])
            
    for cluster in clusters:
        cluster.sort(key=lambda x: len(x.get('body', '')), reverse=True)
    return clusters


initialise_database()

def main():
    try:
        settings = get_system_settings(SHEET_URL)
    except Exception:
        settings = {}
        
    metrics = MetricsCollector.get_instance()
    metrics.set_settings(settings)
    metrics.reset()
    
    issuer_memory = IssuerMemory()
    issuer_memory.load_from_db()
    
    print("[SYSTEM] Bootstrapping core configuration from Google Sheets...")
    try:
        rules = load_rules(SHEET_URL)
        sources = load_sources(SHEET_URL)
        playbooks = load_playbooks(SHEET_URL)
        global_exclusions = load_global_exclusions(SHEET_URL)
        gold_standards = load_gold_standards(SHEET_URL)
        playbook_map = {p['Playbook']: p.get('Questions/Research Steps', '') for p in playbooks}
        document_type_scores = load_document_type_scores(SHEET_URL)
        source_reliability_scores = load_source_reliability(SHEET_URL)
        load_ontology(SHEET_URL)
    except Exception as e:
        save_exception_log(error=f"Failed to load configuration: {e}")
        sys.exit(1)
        
    # --- TASK 1.1: Snapshot and hash the live configuration on every run ---
    canonical_config = {
        "rules": rules,
        "sources": sources,
        "playbooks": playbooks,
        "global_exclusions": global_exclusions,
        "gold_standards": gold_standards,
        "document_type_scores": document_type_scores,
        "source_reliability_scores": source_reliability_scores
    }
    
    # Serialize canonically to ensure stable hashing
    config_json = json.dumps(canonical_config, sort_keys=True)
    config_hash = hashlib.sha256(config_json.encode('utf-8')).hexdigest()
    GLOBAL_MANIFEST_ID = f"CFG-{config_hash[:12].upper()}"
    
    last_snap = get_latest_config_snapshot()
    if not last_snap or last_snap['hash'] != GLOBAL_MANIFEST_ID:
        # Task 1.1 Persistence
        save_config_snapshot(GLOBAL_MANIFEST_ID, metrics.run_id, config_json)
        
        # --- TASK 1.3: Require config changes to go through a reviewed path ---
        if last_snap:
            diff_msg = compute_config_diff(last_snap['config_json'], config_json)
            print(f"\n[CONFIG ALARM] Institutional Rules changed:\n{diff_msg}\n")
            
            # Dispatch human-visible diff alert
            sys_manifest = {
                "manifest_registry": {"decision_id": f"SYS-{GLOBAL_MANIFEST_ID}", "configuration_manifest_hash": GLOBAL_MANIFEST_ID, "execution_timestamp_gmt": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT")},
                "detection_vector": {"detected_event_type": "System Configuration Update", "target_ticker": "SYSTEM"},
                "headline": "Configuration / Rules Pipeline Updated",
                "research_summary": f"System configurations were modified via Google Sheets.\n\nChanges detected:\n{diff_msg}",
                "url": SHEET_URL,
                "is_update": True,
                "evidentiary_provenance_dag": {"supporting_evidence": [], "opposing_evidence": []},
                "syndication_lineage": {"canonical_sensor_id": "SYSTEM"}
            }
            try:
                # Fire an explicit email to operations highlighting the drift
                send_alert(
                    article_title=sys_manifest["headline"],
                    article_url=sys_manifest["url"],
                    event_family=sys_manifest["detection_vector"]["detected_event_type"],
                    confidence=100,
                    research_summary=sys_manifest["research_summary"],
                    evidence_log=[],
                    is_update=True
                )
            except Exception as e:
                print(f" [WARNING] Could not dispatch config alert: {e}")

    ontology_stats = {"total": 0, "extracted": 0, "missed": 0}
    all_new_articles = []
    source_stats = {}
    
    # 1. SENSOR POLLING
    for source in sources:
        is_enabled = str(source.get("Enabled", "")).upper() == "TRUE"
        source_name = source.get("Source", "Unknown")
        rss_url = source.get("RSS URL", "")
        triage_all = str(source.get("Triage All (Email Rejections)", "")).strip().upper() == "TRUE"
        country = source.get("Country", "")
        language = source.get("Language", "")
        
        if is_enabled:
            scraper = get_scraper_for_source(source_name)
            method_used = None
            parsed = []
            parsed_count = 0
            
            if scraper:
                try:
                    parsed, parsed_count = process_custom_scraper(scraper, source_name, rss_url=rss_url, triage_all=triage_all, country=country, language=language)
                    if parsed_count > 0:
                        method_used = "HTML"
                        all_new_articles.extend(parsed)
                        source_stats[source_name] = {"count": parsed_count, "new": len(parsed), "method": method_used}
                except Exception:
                    pass
                    
            if not method_used and rss_url:
                try:
                    parsed, parsed_count = process_1_feed(rss_url, source_name, triage_all, country, language)
                    method_used = "RSS"
                    all_new_articles.extend(parsed)
                    source_stats[source_name] = {"count": parsed_count, "new": len(parsed), "method": method_used}
                except Exception:
                    pass

            try:
                update_last_checked(SHEET_URL, source_name)
            except Exception:
                pass 

    clusters = cluster_articles(all_new_articles)
    
    total_new = 0
    research_queue_rows = [] 
    financials_cache = {} 
    
    # 2. PIPELINE EVALUATION ENGINE
    for cluster in clusters:
        primary = cluster[0]
        body = primary.get("body", "")
        title = primary.get("title", "")
        
        try:
            if not body or len(body) < 100:
                try:
                    scraper = get_scraper_for_source(primary["source_name"])
                    if scraper:
                        fetched = scraper.get_article_body(primary["url"])
                    else:
                        fetched = download_article(primary["url"])
                    if fetched and len(fetched) > 100:
                        primary["body"] = fetched
                        body = fetched
                except Exception:
                    pass
                    
            time.sleep(1)
            
            raw_payload = f"{title}\n\n{body}"
            article_hash = hashlib.sha256(raw_payload.encode('utf-8')).hexdigest()
            event_id, is_new = get_or_create_event(article_hash, raw_payload.encode('utf-8'), "text/plain")
            
            log_sensor_lineage(event_id, primary["source_name"], primary["url"], primary.get("published", ""))
            
            if not is_new:
                continue
                
            capsule = EvidenceCapsule(event_id, primary.get("article_id", "UNKNOWN"), GLOBAL_MANIFEST_ID, raw_payload)

            res = evaluate_capsule(
                capsule=capsule,
                primary=primary,
                rules=rules,
                playbook_map=playbook_map,
                global_exclusions=global_exclusions,
                gold_standards=gold_standards,
                issuer_memory=issuer_memory,
                document_type_scores=document_type_scores,
                ontology_stats=ontology_stats,
                source_reliability_scores=source_reliability_scores,
                research_queue_rows=research_queue_rows,
                financials_cache=financials_cache
            )
            
            total_new += res
            
        except Exception as e:
            continue 

    if research_queue_rows:
        try:
            from src.sheets import batch_append_to_research_queue
            batch_append_to_research_queue(SHEET_URL, research_queue_rows)
        except AttributeError:
            for row in research_queue_rows:
                append_to_research_queue(sheet_url=SHEET_URL, data_row=row)

    issuer_memory.flush_to_sheets()
    prune_daily_memory(SHEET_URL)
    
    total_runtime = time.perf_counter() - metrics.workflow_start
    perform_housekeeping()
    
    # Task 1.1 (DevOps Telemetry Wiring)
    wh = {
        "run_id": metrics.run_id,
        "runtime": total_runtime,
        "workflow_version": GLOBAL_MANIFEST_ID, # Connects DevOps health tracking to strict Configuration Signature
        "git_commit": os.environ.get("GITHUB_SHA", "unknown"),
        "branch": os.environ.get("GITHUB_REF_NAME", "unknown"),
        "python_version": sys.version.split()[0],
        "exception": metrics.exceptions[-1]["exc_type"] if metrics.exceptions else ""
    }
    save_workflow_health(wh)
    
    # Check Statistical Rule Deterioration
    check_pipeline_drift()
    
    from pathlib import Path
    docs_dir = Path("docs")
    docs_dir.mkdir(exist_ok=True)
    docs_path = str(docs_dir / "index.html")
    
    last_publish = get_dashboard_state("last_publish")
    generate_html = False
    pub_interval = metrics.settings.get("Dashboard Publish Interval", 60) * 60
    
    if last_publish:
        age = time.time() - float(last_publish)
        if age > pub_interval:
            generate_html = True
    else:
        generate_html = True
        
    if metrics.exceptions or os.environ.get("FORCE_DASHBOARD") == "true":
        generate_html = True
        
    if generate_html:
        try:
            from src.database import fetch_30_day_baselines
            avg_30, src_30 = fetch_30_day_baselines()
        except ImportError:
            avg_30 = get_30_day_average()
            src_30 = get_30_day_source_averages()
            
        generate_dashboard_html([], output_path=docs_path, metrics=metrics, avg_30=avg_30, src_30=src_30)
        
        archive_json_path = docs_dir / "archive_data.json"
        archive_html_path = docs_dir / "archive.html"
        export_archive_json(filepath=str(archive_json_path))
        generate_archive_html(output_path=str(archive_html_path))
        
        generate_decision_analytics_html(output_path=str(docs_dir / "decision_analytics.html"), metrics=metrics, avg_30=avg_30)
        
        set_dashboard_state("last_publish", time.time())
        
    aggregate_and_sync_yesterday(SHEET_URL)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        traceback.print_exc()
        sys.exit(1)