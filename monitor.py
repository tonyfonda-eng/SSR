import re
import time
import datetime
import os
import sys
import requests
# --- WAF BYPASS WRAPPER ---
_orig_get = requests.get
def _spoofed_get(*args, **kwargs):
    headers = kwargs.get('headers', {})
    if isinstance(headers, dict) and 'User-Agent' not in headers:
        headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    kwargs['headers'] = headers
    return _orig_get(*args, **kwargs)
requests.get = _spoofed_get
# --------------------------

import feedparser
import yfinance as yf
import traceback
from collections import defaultdict
from difflib import SequenceMatcher

from src.config.settings import SHEET_URL
from src.database import (
    initialise_database, article_exists, save_article, article_count,
    track_company, create_event_if_new, log_research, save_reminder,
    get_pending_reminders, mark_reminder_sent, save_lifecycle_logs, 
    get_recent_lifecycle_logs, save_run_metrics, save_ai_usage, 
    save_source_stats, save_workflow_health, save_exception_log,
    perform_housekeeping, get_dashboard_state, set_dashboard_state,
    get_30_day_average, get_30_day_source_averages, export_archive_json
)
from src.scrapers.prnewswire import download_article
from src.scrapers import get_scraper_for_source
from src.sheets import (
    load_rules, load_sources, load_playbooks, append_to_research_queue, 
    update_last_checked, load_global_exclusions, load_gold_standards, 
    log_unknown_event, update_pipeline_metrics, load_daily_memory, 
    batch_append_daily_memory, prune_daily_memory, load_source_reliability, 
    log_ontology_review, load_document_type_scores, aggregate_and_sync_yesterday, 
    get_system_settings
)
from src.rules_engine import evaluate
from src.ai import classify_event, execute_playbook, clients, extract_target_ticker, extract_halt_date
from src.alerts.email import send_alert
from src.issuer import extract_issuing_company
from src.options_calc import calculate_naked_call_roi
from src.drift_monitor import check_pipeline_drift
from src.ontology import extract_concepts, extract_statuses, get_all_matched_terms, load_ontology
from src.financials import get_t12_metrics
from src.monitoring import MetricsCollector
from src.html_generator import generate_dashboard_html, generate_archive_html

class IssuerMemory:
    """In-memory cache of all issuing companies processed today."""
    def __init__(self):
        self.issuers = set()
        self._new_additions = list()

    def load_from_db(self):
        issuers = load_daily_memory(SHEET_URL)
        self.issuers = set([str(k).lower() for k in issuers if k])
        print(f"[DAILY MEMORY] Loaded {len(self.issuers)} issuers from Google Sheets cache.")

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


def _process_article(source_name, article_id, title, url, published, body, rules, playbook_map, global_exclusions=None, gold_standards=None, triage_all=False, issuer_memory=None, document_type=None, country=None, language=None, document_type_scores=None, ontology_stats=None, source_reliability_scores=None):
    start_time = time.perf_counter()
    metrics = MetricsCollector.get_instance()
    metrics.daily["downloaded"] += 1
    metrics.source_stats[source_name]["downloaded"] += 1
    ai_invoked = False
    stage_times = {}
    last_stage_time = start_time

    def mark_stage(stage_name):
        nonlocal last_stage_time
        now = time.perf_counter()
        stage_times[stage_name] = stage_times.get(stage_name, 0) + (now - last_stage_time)
        last_stage_time = now

    def conclude(ret_val, pipeline_stage, outcome, reason, issuer_name="Unknown", event_family="Unknown"):
        mark_stage(pipeline_stage)
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        slowest_stage = max(stage_times, key=stage_times.get) if stage_times else pipeline_stage
        metrics.log_article(article_id, source_name, url, title, country, language, document_type, issuer_name, event_family, pipeline_stage, outcome, reason, ai_invoked, elapsed_ms, slowest_stage)
        return ret_val

    if global_exclusions is None:
        global_exclusions = []

    article_key = f"{source_name}:{article_id}"
    if article_exists(article_key):
        metrics.track_funnel("duplicate_id")
        return conclude(0, 'Database', 'Dropped', 'Duplicate Article')

    if not body:
        metrics.track_funnel("empty_body")
        return conclude(0, 'Download', 'Dropped', 'Empty Body')

    issuer = extract_issuing_company(source_name, title, body)
    if issuer == "EXHAUSTED":
        print("[CRITICAL] AI Providers are exhausted. Aborting ingestion loop.")
        return conclude("ABORT", 'Issuer Extraction', 'Dropped', 'AI Exhausted')

    if issuer_memory and issuer_memory.is_duplicate(issuer):
        print(f"[DAILY MEMORY] Issuer '{issuer}' already processed today. Dropping duplicate syndicated news.")
        metrics.track_funnel("duplicate_issuer")
        save_article(source=source_name, article_id=article_id, title=title, url=url, published=published, body=body)
        return conclude(1, 'Daily Memory', 'Dropped', 'Duplicate Issuer', issuer)

    title_lower = title.lower()
    body_lower = body.lower()

    for ex in global_exclusions:
        ex_lower = str(ex).lower()
        if re.search(r'\b' + re.escape(ex_lower) + r'\b', title_lower) or re.search(r'\b' + re.escape(ex_lower) + r'\b', body_lower):
            print(f"[GLOBAL EXCLUSION] Match found for '{ex}'. Skipping article.")
            metrics.track_funnel("global_exclusion")
            save_article(source=source_name, article_id=article_id, title=title, url=url, published=published, body=body)
            return conclude(1, 'Global Exclusions', 'Dropped', 'Regex Failed', issuer)

    print(f" -> Processing: {title}")

    raw_text = f"{title}\n\n{body}"
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

        if country and country.lower() not in ("us", "usa", "united states"):
            try:
                raw_terms = get_all_matched_terms(raw_text)
                concept_ids = [cid for cid, _ in ontology_concepts]
                log_ontology_review(SHEET_URL, country, source_name, language, document_type, raw_terms, title, url, concept_ids)
            except Exception as e:
                print(f"[WARNING] Ontology review logging failed: {e}")
    except Exception as e:
        print(f"[WARNING] Ontology extraction failed: {e}")

    mark_stage('Ontology')

    article_obj = {"raw_text": raw_text, "document_type": document_type}
    source_rel = 0
    if source_reliability_scores:
        source_rel = source_reliability_scores.get(source_name, 0)

    matches = evaluate(article_obj, rules, document_type_scores if document_type_scores else [], ontology_concepts=ontology_concepts, ontology_statuses=ontology_statuses, source_reliability=source_rel, threshold=10)

    mark_stage('Rules')

    if not matches:
        metrics.track_funnel("rules_rejected")
        return conclude(1, 'Rules Engine', 'Dropped', 'Failed Rules Threshold', issuer, 'Unknown')

    metrics.track_funnel("reached_ai")
    print("[MATCH] High confidence event signals detected!")
    ai_invoked = True
    ticker = extract_target_ticker(body)
    print(f"[AI TICKER] {ticker}")

    if "MOCK AI" in ticker or "ERROR" in ticker or ticker == "EXHAUSTED":
        print("[CRITICAL] AI Providers are exhausted or unavailable.")
        metrics.track_funnel("ai_exhausted")
        return conclude("ABORT", 'Rules Engine', 'Dropped', 'AI Exhausted', issuer)

    if ticker == "PRIVATE":
        print("[AI REJECTED] Target is a private company.")
        metrics.track_funnel("ai_rejected_private")
        save_article(source=source_name, article_id=article_id, title=title, url=url, published=published, body=body)
        return conclude(1, 'AI Classification', 'Dropped', 'Private Company', ticker)

    options_available = False
    market_cap = None
    market_data_str = ""

    if ticker != "UNKNOWN" and "MOCK AI" not in ticker:
        try:
            yf_ticker = yf.Ticker(ticker)
            mc = yf_ticker.info.get('marketCap')
            if mc:
                market_cap = mc
                print(f"[FINANCIALS] Market Cap: ${market_cap:,.2f}")
            
            current_price = yf_ticker.info.get('currentPrice', yf_ticker.info.get('regularMarketPrice'))
            if current_price:
                market_data_str += f"Current Share Price: ${current_price}\n\n"
            
            options = yf_ticker.options
            if options and len(options) > 0:
                options_available = True
                print(f"[OPTIONS] Options chain available. Earliest exp: {options[0]}")
                market_data_str += "Exchange-listed Options Available: YES\n"
            else:
                print(f"[OPTIONS] No options chain found for {ticker}.")
                market_data_str += "Exchange-listed Options Available: NO\n"
        except Exception as e:
            print(f"[WARNING] Failed to fetch financial data for {ticker}: {e}")

    event_family = classify_event(body, matches, ticker=ticker, market_cap=market_cap)
    print(f"[AI CLASSIFICATION] {event_family}")

    if event_family == "EXHAUSTED":
        print("[CRITICAL] AI Providers are exhausted. Aborting ingestion loop.")
        metrics.track_funnel("ai_exhausted")
        return conclude("ABORT", 'AI Classification', 'Dropped', 'AI Exhausted', ticker, event_family)

    if "false positive" in event_family.lower():
        metrics.track_funnel("ai_rejected_false_positive")
        print("[AI REJECTED] Article flagged as false positive.")
        if triage_all:
            print(f"[BYPASS] Source '{source_name}' has Triage All enabled.")
            event_family = "Triage Rejection"
        else:
            save_article(source=source_name, article_id=article_id, title=title, url=url, published=published, body=body)
            return conclude(1, 'AI Classification', 'Dropped', 'AI False Positive', ticker, event_family)

    if event_family.strip().lower() == "unknown":
        print("[UNKNOWN EVENT] Logging to Knowledge Base for review.")
        log_unknown_event(sheet_url=SHEET_URL, source=source_name, article_title=title, article_url=url, rules_score=matches[0]["Score"], ai_response=event_family)
        save_article(source=source_name, article_id=article_id, title=title, url=url, published=published, body=body)
        return conclude(1, 'AI Classification', 'Archived', 'Unknown Event', ticker, event_family)

    if event_family == "M&A Naked Call Strategy" and not options_available:
        print(f"[AI REJECTED] Strategy requires tradable options, but none found for {ticker}.")
        metrics.track_funnel("playbook_rejected")
        save_article(source=source_name, article_id=article_id, title=title, url=url, published=published, body=body)
        return conclude(1, 'AI Classification', 'Dropped', 'No Options Available', ticker, event_family)

    if event_family == "Resumption of Trading":
        halt_date_str = extract_halt_date(body)
        print(f"[T12 METRICS] Calculating structural floor for {ticker} (Halt Date: {halt_date_str})...")
        pre_halt = None
        if ticker != "UNKNOWN":
            try:
                pre_halt = yf.Ticker(ticker).info.get('previousClose')
            except:
                pass
        t12_data = get_t12_metrics(ticker, pre_halt_price=pre_halt, halt_date_str=halt_date_str)
        
        if not t12_data['valid']:
            print(f"[T12 REJECTED] {t12_data.get('reason')}")
            metrics.track_funnel("playbook_rejected")
            save_article(source=source_name, article_id=article_id, url=url, published=published, body=body, title=title)
            return conclude(1, 'Playbook', 'Dropped', 'T12 Structural Floor Failed', ticker, event_family)
            
        print(f"[T12 APPROVED] Net Cash/Share: ${t12_data['net_cash_per_share']:.2f}")
        market_data_str += f"Net Cash Per Share: ${t12_data['net_cash_per_share']:.2f}\n"

    is_update = False
    if ticker != "UNKNOWN" and "MOCK AI" not in ticker:
        print(f"[AI TICKER VERIFIED] Public ticker extracted: {ticker}")
        track_company(ticker)
        event_id, is_new = create_event_if_new(event_family, ticker)
        
        if not is_new:
            print(f"[DEDUPLICATION] Event already tracked. Checking for material updates...")
            material_keywords = ["bump", "increase", "amend", "terminate", "cancel", "regulatory approval", "revised", "superior proposal", "competing", "blocked"]
            is_material = any(kw in body_lower or kw in title_lower for kw in material_keywords)
            
            if is_material:
                print(f"[PYTHON UPDATE] Material update keywords detected. Generating new memo.")
                is_update = True
            else:
                print(f"[PYTHON UPDATE] No material keywords found. Dropping duplicate.")
                metrics.track_funnel("duplicate_event")
                save_article(source=source_name, article_id=article_id, title=title, url=url, published=published, body=body)
                return conclude(1, 'Deduplication', 'Dropped', 'No Material Update', ticker, event_family)
    else:
        event_id = f"UNKNOWN_{article_id}"

    confidence = matches[0]["Score"]
    research_summary = "Playbook not found."
    playbook_steps = playbook_map.get(event_family, "")
    
    if event_family == "Resumption of Trading":
        playbook_steps += "\nCRITICAL T12 INSTRUCTIONS: Why did the halt occur? How long did it last?"
        
    gold_standard = gold_standards.get(event_family) if gold_standards else None
    print(f"[AI RESEARCH] Generating Investment Memo...")
    research_summary = execute_playbook(body, playbook_steps, event_family, gold_standard, market_data_str=market_data_str)
    print(f"[AI RESEARCH] Done.")

    log_research(event_id, article_id, confidence, research_summary)
    
    append_to_research_queue(
        sheet_url=SHEET_URL,
        data_row={
            "timestamp": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            "ticker": ticker,
            "issuer": issuer,
            "event_family": event_family,
            "url": url,
            "status": "Pending"
        }
    )
    
    save_article(source=source_name, article_id=article_id, title=title, url=url, published=published, body=body)

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
    except Exception as e:
        print(f"[ALERT ERROR] Failed to send email alert: {e}")

    go_shop_match = re.search(r'GO-SHOP EXPIRY:\s*(\d{4}-\d{2}-\d{2})', research_summary)
    if go_shop_match:
        expiry_date = go_shop_match.group(1)
        msg = f"Go-Shop period for {ticker} expires TODAY ({expiry_date})."
        save_reminder(event_id, ticker, expiry_date, msg)

    if issuer_memory and issuer != "UNKNOWN":
        issuer_memory.add(issuer)

    return conclude(1, 'Alert', 'Alert Sent', 'Email Dispatched', issuer, event_family)


def process_1_feed(rss_url, source_name, triage_all=False, country=None, language=None):
    print(f"\n[INGESTION] Polling RSS: {source_name} ({rss_url})")
    metrics = MetricsCollector.get_instance()
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(rss_url, headers=headers, timeout=15)
        response.raise_for_status()
        feed = feedparser.parse(response.content)
    except Exception as e:
        print(f"[WARNING] RSS fetch failed for {rss_url}: {e}")
        return [], 0

    parsed_articles = []
    for entry in feed.entries:
        article_id = entry.link.rstrip("/").split("-")[-1].replace(".html", "")
        article_key = f"{source_name}:{article_id}"
        if article_exists(article_key):
            metrics.track_funnel("duplicate_id")
            continue

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
    return parsed_articles, len(feed.entries)


def process_custom_scraper(scraper, source_name, rss_url=None, triage_all=False, country=None, language=None):
    print(f"\n[INGESTION] Polling Custom Scraper: {source_name}")
    metrics = MetricsCollector.get_instance()
    try:
        articles = scraper.get_latest_articles(rss_url=rss_url)
    except Exception as e:
        print(f"[ERROR] Scraper {source_name} failed: {e}")
        return [], 0

    parsed_articles = []
    for i, article in enumerate(articles):
        article_key = f"{source_name}:{article['id']}"
        if article_exists(article_key):
            metrics.track_funnel("duplicate_id")
            continue

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
    print(f"    [{source_name}] Fetched {len(articles)} raw articles, {len(parsed_articles)} parsed.")
    return parsed_articles, len(articles)


def cluster_articles(articles):
    clusters = []
    for article in articles:
        if not article.get('body'):
            continue
        found_cluster = False
        for cluster in clusters:
            rep = cluster[0]
            similarity = SequenceMatcher(None, article['title'].lower(), rep['title'].lower()).ratio()
            if similarity > 0.8:
                cluster.append(article)
                found_cluster = True
                break
        if not found_cluster:
            clusters.append([article])
    
    for cluster in clusters:
        cluster.sort(key=lambda x: len(x.get('body', '')), reverse=True)
    return clusters


from src.database import init_db
init_db()

print("=== Special Situations Radar v1.0.0 ===")
def main():
    try:
        settings = get_system_settings(SHEET_URL)
    except Exception:
        settings = {}
        
    metrics = MetricsCollector.get_instance()
    metrics.set_settings(settings)

    metrics.reset()
    initialise_database()
    
    issuer_memory = IssuerMemory()
    issuer_memory.load_from_db()
    
    pending = get_pending_reminders()
    for rem in pending:
        print(f"[REMINDER] Sending scheduled alert for {rem['event_id']}")
        roi_table = ""
        if rem.get('ticker') and rem['ticker'] != 'UNKNOWN':
            roi_table = calculate_naked_call_roi(rem['ticker'])
        full_message = rem['message'] + "\n\n" + roi_table
        send_alert(
            article_title=f"ACTION REQUIRED: Go-Shop Expiry for {rem['event_id']}",
            article_url="",
            event_family="SYSTEM ALERT",
            confidence=100,
            research_summary=full_message,
            evidence_log=[],
            is_update=False
        )
        mark_reminder_sent(rem['id'])

    rules = load_rules(SHEET_URL)
    sources = load_sources(SHEET_URL)
    playbooks = load_playbooks(SHEET_URL)
    global_exclusions = load_global_exclusions(SHEET_URL)
    gold_standards = load_gold_standards(SHEET_URL)
    playbook_map = {p['Playbook']: p.get('Questions/Research Steps', '') for p in playbooks}
    
    document_type_scores = load_document_type_scores(SHEET_URL)
    source_reliability_scores = load_source_reliability(SHEET_URL)
    
    load_ontology(SHEET_URL)
    ontology_stats = {"total": 0, "extracted": 0, "missed": 0}
    all_new_articles = []
    source_stats = {}

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
                    parsed, parsed_count = process_custom_scraper(
                        scraper, source_name, rss_url=rss_url,
                        triage_all=triage_all, country=country, language=language
                    )
                    metrics.track_funnel("downloaded", parsed_count)
                    if parsed_count > 0:
                        method_used = "HTML"
                        all_new_articles.extend(parsed)
                    source_stats[source_name] = {"count": parsed_count, "new": len(parsed), "method": method_used}
                    print(f"[INGESTION] {source_name}: {parsed_count} fetched, {len(parsed)} new ({method_used})")
                except Exception as e:
                    print(f"[WARNING] HTML Scraper failed for {source_name}: {e}. Falling back to RSS...")

            if not method_used and rss_url:
                try:
                    parsed, parsed_count = process_1_feed(rss_url, source_name, triage_all, country, language)
                    metrics.track_funnel("downloaded", parsed_count)
                    method_used = "RSS"
                    all_new_articles.extend(parsed)
                    source_stats[source_name] = {"count": parsed_count, "new": len(parsed), "method": method_used}
                    print(f"[INGESTION] {source_name}: {parsed_count} fetched, {len(parsed)} new ({method_used})")
                except Exception as e:
                    print(f"[ERROR] RSS Ingestion failed for {source_name}: {e}")

    clusters = cluster_articles(all_new_articles)
    
    clusters_by_source = defaultdict(list)
    for cluster in clusters:
        clusters_by_source[cluster[0]["source_name"]].append(cluster)
    
    MAX_AI_EVALS = 50
    active_sources = list(clusters_by_source.keys())
    source_quotas = {}
    for src in active_sources:
        source_quotas[src] = max(1, MAX_AI_EVALS // max(1, len(active_sources)))
        
    final_clusters = []
    for src in active_sources:
        src_clusters = clusters_by_source[src]
        quota = source_quotas[src]
        final_clusters.extend(src_clusters[:quota])
        
    clusters = final_clusters
    total_new = 0
    
    for cluster in clusters:
        primary = cluster[0]
        body = primary.get("body", "")
        if not body or len(body) < 100:
            try:
                scraper = get_scraper_for_source(primary["source_name"])
                if scraper:
                    fetched = scraper.get_article_body(primary["url"])
                else:
                    fetched = download_article(primary["url"])
                if fetched and len(fetched) > 100:
                    primary["body"] = fetched
            except Exception as e:
                print(f"[WARNING] Lazy fetch failed: {e}")
            time.sleep(1)

        res = _process_article(
            source_name=primary["source_name"],
            article_id=primary["article_id"],
            title=primary["title"],
            url=primary["url"],
            published=primary["published"],
            body=primary["body"],
            rules=rules,
            playbook_map=playbook_map,
            global_exclusions=global_exclusions,
            gold_standards=gold_standards,
            triage_all=primary["triage_all"],
            issuer_memory=issuer_memory,
            document_type=primary.get("document_type"),
            country=primary.get("country"),
            language=primary.get("language"),
            document_type_scores=document_type_scores,
            ontology_stats=ontology_stats,
            source_reliability_scores=source_reliability_scores
        )
        if res == "ABORT":
            break
        total_new += res

    issuer_memory.flush_to_sheets()
    prune_daily_memory(SHEET_URL)
    
    total_runtime = time.perf_counter() - metrics.workflow_start
    metrics.daily["total_runtime_s"] = total_runtime
    
    print("[MONITORING] Writing operational statistics to SQLite...")
    
    log_rows = []
    for art_id, trace in metrics.article_traces.items():
        log_rows.append((
            art_id, trace["timestamp"], trace["source"], trace["title"],
            trace["url"], trace["country"], trace["language"], trace["document_type"],
            trace["issuer"], trace["event_family"], trace["pipeline_stage"],
            trace["outcome"], trace["reason"], trace["ai_invoked"],
            trace["processing_time_ms"], trace["slowest_stage"]
        ))
    save_lifecycle_logs(log_rows)
    perform_housekeeping()
    
    metrics.daily["run_id"] = metrics.run_id
    metrics.daily["timestamp"] = datetime.datetime.utcnow().isoformat()
    save_run_metrics(metrics.daily)
    
    ai_rows = []
    for key_id, ai in metrics.ai_telemetry.items():
        ai_rows.append((
            metrics.run_id, metrics.daily["timestamp"], ai["provider"],
            ai["key_id"], ai["requests"], ai["success"], ai["failures"], ai["errors_429"],
            ai["errors_503"], ai["timeouts"], ai["retries"], ai["fallbacks"], ai["response_time_sum"],
            ai["max_latency"], ai["last_success_ts"], ai["last_failure_ts"]
        ))
    save_ai_usage(ai_rows)
    
    src_rows = []
    for src, st in metrics.source_stats.items():
        src_rows.append((
            metrics.run_id, metrics.daily["timestamp"], src,
            st["downloaded"], st["survived_regex"], st["survived_ontology"], st["survived_rules"],
            st["reached_ai"], st["alerts"], st["processing_time_sum"], st["processed_count"]
        ))
    save_source_stats(src_rows)
    
    wh = {
        "run_id": metrics.run_id,
        "date": datetime.datetime.utcnow().strftime("%Y-%m-%d"),
        "timestamp": metrics.daily["timestamp"],
        "success": 1 if not metrics.exceptions else 0,
        "failed": 1 if metrics.exceptions else 0,
        "runtime": total_runtime,
        "articles": metrics.daily["articles_processed_count"],
        "emails": metrics.daily["emails_sent"],
        "git_commit": os.environ.get("GITHUB_SHA", "unknown"),
        "branch": os.environ.get("GITHUB_REF_NAME", "unknown"),
        "python_version": sys.version.split()[0],
        "exception": metrics.exceptions[-1]["exc_type"] if metrics.exceptions else "",
        "workflow_version": "1.0",
        "run_number": os.environ.get("GITHUB_RUN_NUMBER", "1")
    }
    save_workflow_health(wh)
    
    for exc in metrics.exceptions:
        save_exception_log(metrics.run_id, exc["timestamp"], exc["exc_type"], exc["stack_trace"], exc["module"], exc["func_name"], exc["article_url"], exc["severity"])

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
        print("[MONITORING] Generating HTML Dashboard and Archive...")
        logs = get_recent_lifecycle_logs()
        metrics.calculate_health_score(total_runtime)
        
        # --- NEW: Anomaly Engine Baselines ---
        try:
            from src.database import fetch_30_day_baselines
            avg_30, src_30 = fetch_30_day_baselines()
        except ImportError:
            # Fallback if the new function isn't imported correctly yet
            avg_30 = get_30_day_average()
            src_30 = get_30_day_source_averages()

        # --- NEW: Next Schedule Prediction ---
        # Predicts next run based on a standard 3-hour interval
        metrics.next_run_str = (datetime.datetime.utcnow() + datetime.timedelta(hours=3)).strftime("%Y-%m-%d %H:%M UTC")
        
        # Generate the Executive Summary
        generate_dashboard_html(logs, output_path=docs_path, metrics=metrics, avg_30=avg_30, src_30=src_30)
        
        # Generate the Archive
        archive_json_path = docs_dir / "archive_data.json"
        archive_html_path = docs_dir / "archive.html"
        export_archive_json(filepath=str(archive_json_path))
        generate_archive_html(output_path=str(archive_html_path))
        
        set_dashboard_state("last_publish", time.time())
    else:
        print("[MONITORING] Skipping HTML Dashboard generation (throttle).")

    print("[MONITORING] Checking if yesterday's data needs syncing to Google Sheets...")
    aggregate_and_sync_yesterday(SHEET_URL)
    
    # Check if we should generate the Weekly Operations Report (runs on Saturdays)
    if datetime.datetime.utcnow().weekday() == 5:
        try:
            last_report = get_dashboard_state("last_weekly_report")
            today_str = datetime.datetime.utcnow().strftime("%Y-%m-%d")
            if last_report != today_str:
                from src.reporting import generate_weekly_report
                generate_weekly_report()
                set_dashboard_state("last_weekly_report", today_str)
        except Exception as e:
            print(f"[WARNING] Failed to generate weekly report: {e}")
    print(f"[DAILY MEMORY] Session ended with {issuer_memory.size} issuers cached.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        traceback.print_exc()
        print(f"\n[FATAL ERROR] {e}")
        sys.exit(1)