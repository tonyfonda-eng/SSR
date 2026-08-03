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

# Updated to use SSR 2.0 Canonical DB Methods
from src.database import (
    initialise_database, get_or_create_event, log_sensor_lineage,
    log_transformation, commit_decision_capsule, register_configuration_manifest,
    save_workflow_health, save_exception_log, save_ai_usage,
    save_source_stats, get_dashboard_state, set_dashboard_state,
    get_recent_lifecycle_logs, export_archive_json, get_30_day_average,
    get_30_day_source_averages, perform_housekeeping, get_pending_reminders,
    mark_reminder_sent, save_reminder, log_research, track_company, create_event_if_new
)

from src.scrapers.prnewswire import download_article
from src.scrapers import get_scraper_for_source
from src.sheets import (
    load_rules, load_sources, load_playbooks, append_to_research_queue,
    update_last_checked, load_global_exclusions, load_gold_standards,
    log_unknown_event, update_pipeline_metrics, load_daily_memory,
    batch_append_daily_memory, prune_daily_memory,
    load_source_reliability, log_ontology_review, load_document_type_scores,
    aggregate_and_sync_yesterday, get_system_settings
)
from src.rules_engine import evaluate
from src.ai import classify_event, execute_playbook, extract_target_ticker, extract_halt_date
from src.alerts.email import send_alert
from src.issuer import extract_issuing_company
from src.options_calc import calculate_naked_call_roi
from src.drift_monitor import check_pipeline_drift
from src.ontology import extract_concepts, extract_statuses, get_all_matched_terms, load_ontology
from src.financials import get_t12_metrics
from src.monitoring import MetricsCollector
from src.html_generator import generate_dashboard_html, generate_archive_html, generate_decision_analytics_html


class EvidenceCapsule:
    """
    SSR 2.0 Core Paradigm: The Immutable Evidence Capsule.
    Replaces loose variables. Accumulates Facts, Derived Facts, and Probabilistic Interpretations.
    """
    def __init__(self, event_id: str, manifest_hash: str, raw_text: str):
        self.decision_id = f"DSC-{uuid.uuid4()}"
        self.event_id = event_id
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
        """Serializes the Canonical Decision Manifest for public API / Database consumption."""
        return {
            "manifest_registry": {
                "decision_id": self.decision_id,
                "event_id": self.event_id,
                "configuration_manifest_hash": self.manifest_hash,
                "execution_timestamp_gmt": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT"),
                "evidence_completeness_score": self.completeness_score
            },
            "detection_vector": {
                "outcome": self.outcome,
                "terminal_stage": self.terminal_stage,
                "detected_event_type": self.event_family,
                "target_ticker": self.ticker
            },
            "performance_telemetry_ms": self.timings,
            "evidentiary_provenance_dag": {
                "supporting_evidence": self.evidence["SUPPORTING"],
                "opposing_evidence": self.evidence["OPPOSING"]
            }
        }


class IssuerMemory:
    """In-memory cache of all issuing companies processed today."""
    def __init__(self):
        self.issuers = set()
        self._new_additions = list()

    def load_from_db(self):
        issuers = load_daily_memory(SHEET_URL)
        self.issuers = set([str(k).lower() for k in issuers if k])
        print(f" [DAILY MEMORY] Loaded {len(self.issuers)} issuers from Google Sheets cache.")

    def is_duplicate(self, issuer):
        if not issuer or issuer == "UNKNOWN":
            return False
        return issuer.lower() in self.issuers

    def add(self, issuer):
        if issuer and issuer != "UNKNOWN":
            key_lower = issuer.lower()
            if key_lower not in self.issuers:
                self.issuers.add(key_lower)
                self._new_additions.append(issuer)

    def flush_to_sheets(self):
        if self._new_additions:
            batch_append_daily_memory(SHEET_URL, self._new_additions)
            self._new_additions.clear()

    @property
    def size(self):
        return len(self.issuers)


def evaluate_capsule(capsule: EvidenceCapsule, primary: dict, rules, playbook_map, global_exclusions, gold_standards,
                     issuer_memory, document_type_scores, ontology_stats, source_reliability_scores, 
                     research_queue_rows, financials_cache):
    """
    SSR 2.0 Decoupled Pipeline Evaluation Engine.
    Processes the immutable capsule and commits exactly at the short-circuit termination boundary.
    """
    metrics = MetricsCollector.get_instance()
    
    source_name = primary["source_name"]
    url = primary["url"]
    title = primary["title"]
    body = primary["body"]
    triage_all = primary.get("triage_all", False)
    document_type = primary.get("document_type")
    country = primary.get("country")
    language = primary.get("language")
    
    metrics.daily["downloaded"] += 1
    if source_name not in metrics.source_stats:
        metrics.source_stats[source_name] = defaultdict(int)
    metrics.source_stats[source_name]["downloaded"] += 1

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
            "performance_telemetry_ms": capsule.timings
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
        if ontology_stats is not None:
            ontology_stats["total"] += 1
            if ontology_concepts:
                ontology_stats["extracted"] += 1
            else:
                ontology_stats["missed"] += 1
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
                       source_reliability=source_rel, threshold=10)
    capsule.mark_timing("rules_ms")
    
    if not matches:
        metrics.track_funnel("rules_rejected")
        capsule.append_evidence("OPPOSING", "Rules Engine", "Deterministic Evaluator", "Failed Rules Threshold (<10)", 1.0)
        return flush_termination("DROPPED", "Rules Engine")
    
    capsule.append_evidence("SUPPORTING", "Rules Engine", "Deterministic Evaluator", f"Passed threshold with Score: {matches[0]['Score']}", 1.0)

    # --- AI Inference Phase ---
    metrics.track_funnel("reached_ai")
    print(" [MATCH] High confidence event signals detected!")
    
    ticker = extract_target_ticker(body)
    capsule.ticker = ticker
    print(f" [AI TICKER] {ticker}")
    
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
        else:
            try:
                time.sleep(0.5)
                yf_ticker = yf.Ticker(ticker)
                ticker_info = yf_ticker.info
                options = yf_ticker.options
                if financials_cache is not None:
                    financials_cache[ticker] = {"info": ticker_info, "options": options}
            except Exception as e:
                capsule.completeness_score = 0.86
                capsule.append_evidence("OPPOSING", "Financials", "Yahoo API", f"Financial Data Missing: {e}", 0.5)
                ticker_info, options = None, []

        if ticker_info:
            mc = ticker_info.get('marketCap')
            if mc:
                market_cap = mc
                market_data_str += f"Current Market Cap: ${market_cap:,.2f}\n"
            current_price = ticker_info.get('currentPrice', ticker_info.get('regularMarketPrice'))
            if current_price:
                market_data_str += f"Current Share Price: ${current_price}\n\n"
                
        if options and len(options) > 0:
            options_available = True
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
        "aggregate_confidence": matches[0]["Score"] / 100.0 if matches[0]["Score"] else 0.5
    }
    
    print(f" [AI CLASSIFICATION] {event_family}")
    
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
                          rules_score=matches[0]["Score"], ai_response=event_family)
        return flush_termination("ARCHIVED", "AI Classification")

    if event_family == "M&A Naked Call Strategy" and not options_available:
        metrics.track_funnel("playbook_rejected")
        capsule.append_evidence("OPPOSING", "Financial Verification", "Options Check", "No Tradable Options Found", 1.0)
        return flush_termination("DROPPED", "Financial Verification")

    if event_family == "Resumption of Trading":
        halt_date_str = extract_halt_date(body)
        pre_halt = ticker_info.get('previousClose') if ticker_info else None
        t12_data = get_t12_metrics(ticker, pre_halt_price=pre_halt, halt_date_str=halt_date_str)
        if not t12_data['valid']:
            metrics.track_funnel("playbook_rejected")
            capsule.append_evidence("OPPOSING", "Financial Verification", "T12 Structural Floor", f"Floor failed: {t12_data.get('reason')}", 1.0)
            return flush_termination("DROPPED", "Financial Verification")
            
        capsule.append_evidence("SUPPORTING", "Financial Verification", "T12 Engine", f"Net Cash/Share: ${t12_data['net_cash_per_share']:.2f}", 1.0)
        market_data_str += f"Net Cash Per Share: ${t12_data['net_cash_per_share']:.2f}\n"

    # --- Action / Dispatch Phase ---
    is_update = False
    if ticker != "UNKNOWN" and "MOCK AI" not in ticker:
        track_company(ticker)
        event_id, is_new = create_event_if_new(event_family, ticker)
        
        if not is_new:
            material_keywords = ["bump", "increase", "amend", "terminate", "cancel", "regulatory approval", "revised", "superior proposal", "competing", "blocked"]
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

    confidence = matches[0]["Score"]
    playbook_steps = playbook_map.get(event_family, "")
    if event_family == "Resumption of Trading":
        playbook_steps += "\nCRITICAL T12 INSTRUCTIONS: Why did the halt occur? How long did it last?"
        
    gold_standard = gold_standards.get(event_family) if gold_standards else None
    
    print(f" [AI RESEARCH] Generating Investment Memo...")
    research_summary = execute_playbook(body, playbook_steps, event_family, gold_standard, market_data_str=market_data_str)
    print(f" [AI RESEARCH] Done.")
    
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
        print(f" [ALERT ERROR] Failed to send email alert: {e}")
        
    go_shop_match = re.search(r'GO-SHOP EXPIRY:\s*(\d{4}-\d{2}-\d{2})', research_summary)
    if go_shop_match:
        expiry_date = go_shop_match.group(1)
        save_reminder(event_id, ticker, expiry_date, f"Go-Shop period for {ticker} expires TODAY ({expiry_date}).")
        
    if issuer_memory and issuer != "UNKNOWN":
        issuer_memory.add(issuer)
        
    return flush_termination("DETECTED", "Complete")


def process_1_feed(rss_url, source_name, triage_all=False, country=None, language=None):
    print(f"\n[INGESTION] Polling RSS: {source_name} ({rss_url})")
    metrics = MetricsCollector.get_instance()
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(rss_url, headers=headers) 
        response.raise_for_status()
        feed = feedparser.parse(response.content)
    except Exception as e:
        error_msg = f"RSS fetch failed for {rss_url}: {e}"
        print(f" [WARNING] {error_msg}")
        save_exception_log(error=error_msg)
        if hasattr(metrics, 'log_error'):
            metrics.log_error("RSS", error_msg)
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
    print(f"\n[INGESTION] Polling Custom Scraper: {source_name}")
    metrics = MetricsCollector.get_instance()
    try:
        articles = scraper.get_latest_articles(rss_url=rss_url)
    except Exception as e:
        error_msg = f"Scraper {source_name} failed: {e}"
        print(f" [ERROR] {error_msg}")
        save_exception_log(error=error_msg)
        if hasattr(metrics, 'log_error'):
            metrics.log_error("Parser", error_msg)
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
        
    print(f" [{source_name}] Fetched {len(articles)} raw articles, {len(parsed_articles)} parsed.")
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


from src.database import initialise_database
initialise_database()
print("=== Special Situations Radar v2.0.0 (The Evidence Engine) ===")

def main():
    try:
        settings = get_system_settings(SHEET_URL)
    except Exception:
        settings = {}
        
    metrics = MetricsCollector.get_instance()
    metrics.set_settings(settings)
    metrics.reset()
    
    # Register the System State Configuration Manifest for this Execution Run
    manifest_data = {
        "parser_version": "2.0.0",
        "transformation_dag_version": "2.0.0",
        "ontology_version": "2.0.0",
        "rule_pack_version": "2.0.0",
        "prompt_version": "2.0.0",
        "playbook_version": "2.0.0"
    }
    GLOBAL_MANIFEST_ID = register_configuration_manifest(manifest_data)
    
    issuer_memory = IssuerMemory()
    issuer_memory.load_from_db()
    
    pending = get_pending_reminders()
    for rem in pending:
        print(f" [REMINDER] Sending scheduled alert...")
        send_alert(
            article_title=f"ACTION REQUIRED: Go-Shop Expiry for Targeted Event",
            article_url="",
            event_family="SYSTEM ALERT",
            confidence=100,
            research_summary=rem,
            evidence_log=[],
            is_update=False
        )
        # Note: Reminder marking signature may require adjustment based on specific legacy sheet needs
        try:
            mark_reminder_sent(rem)
        except Exception:
            pass
            
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
        error_msg = f"Failed to load core system configuration from Google Sheets: {e}"
        print(f"[FATAL ERROR] {error_msg}")
        save_exception_log(error=error_msg)
        sys.exit(1)
        
    ontology_stats = {"total": 0, "extracted": 0, "missed": 0}
    all_new_articles = []
    source_stats = {}
    
    # 1. SENSOR POLLING (Ingestion & Lineage Creation)
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
                    metrics.track_funnel("downloaded", parsed_count)
                    if parsed_count > 0:
                        method_used = "HTML"
                        all_new_articles.extend(parsed)
                        source_stats[source_name] = {"count": parsed_count, "new": len(parsed), "method": method_used}
                except Exception as e:
                    print(f" [WARNING] HTML Scraper failed for {source_name}: {e}. Falling back to RSS...")
                    
            if not method_used and rss_url:
                try:
                    parsed, parsed_count = process_1_feed(rss_url, source_name, triage_all, country, language)
                    metrics.track_funnel("downloaded", parsed_count)
                    method_used = "RSS"
                    all_new_articles.extend(parsed)
                    source_stats[source_name] = {"count": parsed_count, "new": len(parsed), "method": method_used}
                except Exception as e:
                    print(f" [ERROR] RSS Ingestion failed for {source_name}: {e}")

            try:
                update_last_checked(SHEET_URL, source_name)
            except Exception:
                pass 

    clusters = cluster_articles(all_new_articles)
    
    total_new = 0
    research_queue_rows = [] 
    financials_cache = {} 
    
    # 2. PIPELINE EVALUATION ENGINE (Evidence Capsule Routing)
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
                except Exception as e:
                    print(f" [WARNING] Lazy fetch failed: {e}")
                    
            time.sleep(1)
            
            # --- SSR 2.0 Ingestion Repository & Fingerprinting ---
            raw_payload = f"{title}\n\n{body}"
            article_hash = hashlib.sha256(raw_payload.encode('utf-8')).hexdigest()
            event_id, is_new = get_or_create_event(article_hash, raw_payload.encode('utf-8'), "text/plain")
            
            log_sensor_lineage(event_id, primary["source_name"], primary["url"], primary.get("published", ""))
            
            if not is_new:
                metrics.track_funnel("duplicate_id")
                continue
                
            # Initialize Immutable Tracking Capsule
            capsule = EvidenceCapsule(event_id, GLOBAL_MANIFEST_ID, raw_payload)

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
            error_msg = f"Catastrophic failure processing article {primary.get('article_id')}: {e}"
            print(f" [CRITICAL ARTICLE ERROR] {error_msg}")
            save_exception_log(error=error_msg)
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
    metrics.daily["total_runtime_s"] = total_runtime
    print("[MONITORING] Writing devops operational statistics to SQLite...")
    
    perform_housekeeping()
    
    metrics.daily["run_id"] = metrics.run_id
    metrics.daily["timestamp"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT")
    save_run_metrics(metrics.daily)
    
    ai_rows = []
    for key_id, ai in metrics.ai_telemetry.items():
        ai_rows.append((
            metrics.run_id, metrics.daily["timestamp"], ai["provider"], ai["key_id"], 
            ai["requests"], ai["success"], ai["failures"], ai["errors_429"], ai["errors_503"], 
            ai["timeouts"], ai["retries"], ai["fallbacks"], ai["response_time_sum"],
            ai["max_latency"], ai["last_success_ts"], ai["last_failure_ts"]
        ))
    save_ai_usage(ai_rows)
    
    src_rows = []
    for src, st in metrics.source_stats.items():
        src_rows.append((
            metrics.run_id, metrics.daily["timestamp"], src, st.get("downloaded", 0), 
            st.get("survived_regex", 0), st.get("survived_ontology", 0), st.get("survived_rules", 0),
            st.get("reached_ai", 0), st.get("alerts", 0), st.get("processing_time_sum", 0),
            st.get("processed_count", 0)
        ))
    save_source_stats(src_rows)
    
    wh = {
        "run_id": metrics.run_id,
        "date": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
        "timestamp": metrics.daily["timestamp"],
        "success": 1 if not metrics.exceptions else 0,
        "failed": 1 if metrics.exceptions else 0,
        "runtime": total_runtime,
        "articles": metrics.daily.get("articles_processed_count", 0),
        "emails": metrics.daily.get("emails_sent", 0),
        "git_commit": os.environ.get("GITHUB_SHA", "unknown"),
        "branch": os.environ.get("GITHUB_REF_NAME", "unknown"),
        "python_version": sys.version.split()[0],
        "exception": metrics.exceptions[-1]["exc_type"] if metrics.exceptions else "",
        "workflow_version": "2.0",
        "run_number": os.environ.get("GITHUB_RUN_NUMBER", "1")
    }
    save_workflow_health(wh)
    
    for exc in metrics.exceptions:
        save_exception_log(
            metrics.run_id, exc["timestamp"], exc["exc_type"], exc["stack_trace"], 
            exc["module"], exc["func_name"], exc["article_url"], exc["severity"]
        )
        
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
        print("[MONITORING] Triggering Decoupled Asset Compilation (HTML Manifest Readers)...")
        logs = get_recent_lifecycle_logs()
        metrics.calculate_health_score(total_runtime)
        
        try:
            from src.database import fetch_30_day_baselines
            avg_30, src_30 = fetch_30_day_baselines()
        except ImportError:
            avg_30 = get_30_day_average()
            src_30 = get_30_day_source_averages()
            
        metrics.next_run_str = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S GMT")
        
        generate_dashboard_html(logs, output_path=docs_path, metrics=metrics, avg_30=avg_30, src_30=src_30)
        
        archive_json_path = docs_dir / "archive_data.json"
        archive_html_path = docs_dir / "archive.html"
        export_archive_json(filepath=str(archive_json_path))
        generate_archive_html(output_path=str(archive_html_path))
        
        generate_decision_analytics_html(output_path=str(docs_dir / "decision_analytics.html"), metrics=metrics, avg_30=avg_30)
        
        set_dashboard_state("last_publish", time.time())
    else:
        print("[MONITORING] Skipping HTML Dashboard generation (throttle).")
        
    print("[MONITORING] Checking if yesterday's data needs syncing to Google Sheets...")
    aggregate_and_sync_yesterday(SHEET_URL)
    
    if datetime.datetime.now(datetime.timezone.utc).weekday() == 5:
        try:
            last_report = get_dashboard_state("last_weekly_report")
            today_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
            if last_report != today_str:
                from src.reporting import generate_weekly_report
                generate_weekly_report()
                set_dashboard_state("last_weekly_report", today_str)
        except Exception as e:
            print(f" [WARNING] Failed to generate weekly report: {e}")
            
    print(f" [DAILY MEMORY] Session ended with {issuer_memory.size} issuers cached.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        traceback.print_exc()
        print(f"\n [FATAL ERROR] {e}")
        sys.exit(1)