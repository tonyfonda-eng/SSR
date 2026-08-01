import re
import feedparser
from src.config.settings import SHEET_URL
import time
import datetime
from difflib import SequenceMatcher
from src.database import (
    initialise_database,
    article_exists,
    save_article,
    article_count,
    track_company,
    create_event_if_new,
    log_research,
    save_reminder,
    get_pending_reminders,
    mark_reminder_sent,
)
from src.scrapers.prnewswire import download_article
from src.scrapers import get_scraper_for_source
from src.sheets import (
    load_rules, load_sources, load_playbooks,
    append_to_research_queue, update_last_checked, load_global_exclusions,
    load_gold_standards, log_unknown_event, update_pipeline_metrics,
    load_daily_memory, batch_append_daily_memory, prune_daily_memory,
    load_source_reliability, log_ontology_review
)
from src.rules_engine import evaluate
from src.ai import classify_event, execute_playbook, clients
from src.alerts.email import send_alert
from src.issuer import extract_issuing_company
from src.options_calc import calculate_naked_call_roi

# --- Daily Issuer Memory ---
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


def _process_article(source_name, article_id, title, url, published,
                    body, rules, playbook_map, global_exclusions=None, gold_standards=None,
                    triage_all=False, funnel_metrics=None, issuer_memory=None,
                    document_type=None, country=None, language=None,
                    document_type_scores=None, ontology_stats=None,
                    source_reliability_scores=None):
    import time
    start_time = time.perf_counter()
    from src.monitoring import MetricsCollector
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

    def conclude(ret_val, pipeline_stage, outcome, reason,
                issuer_name="Unknown", event_family="Unknown"):
        mark_stage(pipeline_stage)
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        slowest_stage = max(stage_times, key=stage_times.get) if stage_times else pipeline_stage
        metrics.log_article(article_id, source_name, url, title,
                            country, language, document_type, issuer_name, event_family,
                            pipeline_stage, outcome, reason, ai_invoked, elapsed_ms, slowest_stage)
        return ret_val

    if global_exclusions is None:
        global_exclusions = []
        
    article_key = f"{source_name}:{article_id}"
    
    # 1. Check persistent SQLite dedup
    if article_exists(article_key):
        return conclude(0, 'Database', 'Dropped', 'Duplicate Article')

    if not body:
        if funnel_metrics:
            funnel_metrics[3] += 1
        return conclude(0, 'Download', 'Dropped', 'Empty Body')

    if funnel_metrics: 
        funnel_metrics[2] += 1

    # 2. Extract Issuer and Dedupe
    issuer = extract_issuing_company(source_name, title, body)
    if issuer == "EXHAUSTED":
        print("[CRITICAL] AI Providers are exhausted. Aborting ingestion loop.")
        return conclude("ABORT", 'Issuer Extraction', 'Dropped', 'AI Exhausted')

    if issuer_memory and issuer_memory.is_duplicate(issuer):
        print(f"[DAILY MEMORY] Issuer '{issuer}' already processed today. Dropping duplicate syndicated news.")
        save_article(
            source=source_name,
            article_id=article_id,
            title=title,
            url=url,
            published=published,
            body=body,
        )
        return conclude(1, 'Daily Memory', 'Dropped', 'Duplicate Issuer', issuer)

    # Global Exclusion Pre-Filter
    title_lower = title.lower()
    body_lower = body.lower()
    for ex in global_exclusions:
        import re
        ex_lower = ex.lower()
        if re.search(r'\b' + re.escape(ex_lower) + r'\b', title_lower) \
           or re.search(r'\b' + re.escape(ex_lower) + r'\b', body_lower):
            print(f"[GLOBAL EXCLUSION] Match found for '{ex}'. Skipping article.")
            save_article(
                source=source_name,
                article_id=article_id,
                title=title,
                url=url,
                published=published,
                body=body,
            )
            return conclude(1, 'Global Exclusions', 'Dropped', 'Regex Failed', issuer)

    if funnel_metrics: 
        funnel_metrics[4] += 1

    print(f" -> Processing: {title}")

    # Cash Event Detection (Stage 1)
    from src.ontology import extract_concepts, extract_statuses, get_all_matched_terms
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
                log_ontology_review(SHEET_URL, country, source_name,
                                  language, document_type, raw_terms, title, url, concept_ids)
            except Exception as e:
                print(f"[WARNING] Ontology review logging failed: {e}")
    except Exception as e:
        print(f"[WARNING] Ontology extraction failed: {e}")

    mark_stage('Ontology')
    article_obj = {
        "raw_text": raw_text,
        "document_type": document_type
    }

    source_rel = 0
    if source_reliability_scores:
        source_rel = source_reliability_scores.get(source_name, 0)

    matches = evaluate(article_obj, rules, document_type_scores if document_type_scores else {},
                       ontology_concepts=ontology_concepts,
                       ontology_statuses=ontology_statuses,
                       source_reliability=source_rel, threshold=10)
    mark_stage('Rules')

    if matches:
        if funnel_metrics: 
            funnel_metrics[5] += 1
        print("[MATCH] High confidence event signals detected!")

        # Ticker Verification (Stage 2)
        from src.ai import extract_target_ticker
        ai_invoked = True
        ticker = extract_target_ticker(body)
        print(f"[AI TICKER] {ticker}")

        if "MOCK AI" in ticker or "ERROR" in ticker or ticker == "UNKNOWN" or ticker == "EXHAUSTED":
            print("[CRITICAL] AI Providers are exhausted or unavailable.")
            return conclude("ABORT", 'Rules Engine', 'Dropped', 'AI Exhausted', issuer)

        if ticker == "PRIVATE":
            print("[AI REJECTED] Target is a private company.")
            save_article(
                source=source_name,
                article_id=article_id,
                title=title,
                url=url,
                published=published,
                body=body,
            )
            return conclude(1, 'AI Classification', 'Dropped', 'Private Company', ticker)

        if funnel_metrics: 
            funnel_metrics[6] += 1

        options_available = False
        market_cap = None
        market_data_str = ""

        if ticker != "UNKNOWN" and "MOCK AI" not in ticker:
            import yfinance as yf
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
                    market_data_str += f"Exchange-listed Options Available: YES\n"
                else:
                    print(f"[OPTIONS] No options chain found for {ticker}.")
                    market_data_str += f"Exchange-listed Options Available: NO\n"
            except Exception as e:
                print(f"[WARNING] Failed to fetch financial data for {ticker}: {e}")

        # Classification (Stage 3)
        event_family = classify_event(body, matches, ticker=ticker, market_cap=market_cap)
        print(f"[AI CLASSIFICATION] {event_family}")

        if "Unknown" in event_family or event_family == "EXHAUSTED":
            print("[CRITICAL] AI Providers are exhausted. Aborting ingestion loop.")
            return conclude("ABORT", 'AI Classification', 'Dropped', 'AI Exhausted', ticker, event_family)

        if "false positive" in event_family.lower():
            print("[AI REJECTED] Article flagged as false positive.")
            if triage_all:
                print(f"[BYPASS] Source '{source_name}' has Triage All enabled.")
                event_family = "Triage Rejection"
            else:
                save_article(
                    source=source_name,
                    article_id=article_id,
                    title=title,
                    url=url,
                    published=published,
                    body=body,
                )
                return conclude(1, 'AI Classification', 'Dropped', 'AI False Positive', ticker, event_family)

        if event_family.strip().lower() == "unknown":
            print("[UNKNOWN EVENT] Logging to Knowledge Base for review.")
            log_unknown_event(
                sheet_url=SHEET_URL,
                source=source_name,
                article_title=title,
                article_url=url,
                rules_score=matches[0]["Score"],
                ai_response=event_family
            )
            save_article(
                source=source_name,
                article_id=article_id,
                title=title,
                url=url,
                published=published,
                body=body,
            )
            return conclude(1, 'AI Classification', 'Archived', 'Unknown Event', ticker, event_family)

        if event_family == "M&A Naked Call Strategy" and not options_available:
            print(f"[AI REJECTED] Strategy requires tradable options, but none found for {ticker}.")
            save_article(
                source=source_name,
                article_id=article_id,
                title=title,
                url=url,
                published=published,
                body=body,
            )
            return conclude(1, 'AI Classification', 'Dropped', 'No Options Available', ticker, event_family)

        if event_family == "Resumption of Trading":
            from src.financials import get_t12_metrics
            from src.ai import extract_halt_date
            halt_date_str = extract_halt_date(body)
            print(f"[T12 METRICS] Calculating structural floor for {ticker} (Halt Date: {halt_date_str})...")
            
            pre_halt = None
            if ticker != "UNKNOWN":
                try:
                    import yfinance as yf
                    pre_halt = yf.Ticker(ticker).info.get('previousClose')
                except:
                    pass

            t12_data = get_t12_metrics(ticker, pre_halt_price=pre_halt, halt_date_str=halt_date_str)
            if not t12_data['valid']:
                print(f"[T12 REJECTED] {t12_data.get('reason')}")
                save_article(
                    source=source_name, article_id=article_id,
                    url=url, published=published, body=body
                )
                return conclude(1, 'Playbook', 'Dropped', 'T12 Structural Floor Failed', ticker, event_family)
            
            print(f"[T12 APPROVED] Net Cash/Share: ${t12_data['net_cash_per_share']:.2f}")
            market_data_str = f"Net Cash Per Share: ${t12_data['net_cash_per_share']:.2f}\n"

        if funnel_metrics and options_available: 
            funnel_metrics[7] += 1

        is_update = False
        if ticker != "UNKNOWN" and "MOCK AI" not in ticker:
            print(f"[AI TICKER VERIFIED] Public ticker extracted: {ticker}")
            track_company(ticker)
            event_id, is_new = create_event_if_new(event_family, ticker)
            if not is_new:
                print(f"[DEDUPLICATION] Event already tracked. Checking for material updates...")
                material_keywords = ["bump", "increase", "amend", "terminate", "cancel", "revised", "superior proposal", "competing", "regulatory approval", "blocked"]
                body_lower = body.lower()
                title_lower = title.lower()
                is_material = any(kw in body_lower or kw in title_lower for kw in material_keywords)
                if is_material:
                    print(f"[PYTHON UPDATE] Material update keywords detected. Generating new memo.")
                    is_update = True
                else:
                    print(f"[PYTHON UPDATE] No material keywords found. Dropping duplicate.")
                    save_article(
                        source=source_name,
                        article_id=article_id,
                        title=title,
                        url=url,
                        published=published,
                        body=body,
                    )
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

        if funnel_metrics and is_update: 
            funnel_metrics[9] += 1

        log_research(event_id, article_id, confidence, research_summary)
        if funnel_metrics: 
            funnel_metrics[10] += 1

        append_to_research_queue(
            sheet_url=SHEET_URL,
            article_title=title,
            article_url=url,
            event_family=event_family,
            confidence=confidence
        )
        
        save_article(
            source=source_name,
            article_id=article_id,
            title=title,
            url=url,
            published=published,
            body=body,
        )

        try:
            send_alert(
                article_title=title,
                article_url=url,
                event_family=event_family,
                confidence=confidence,
                research_summary=research_summary,
                evidence_log=matches[0].get("_Evidence", []),
                is_update=is_update,
            )
            if funnel_metrics: 
                funnel_metrics[11] += 1
        except Exception as e:
            print(f"[ALERT ERROR] Failed to send email alert: {e}")

        go_shop_match = re.search(r'GO-SHOP EXPIRY:\s*(\d{4}-\d{2}-\d{2})', research_summary)
        if go_shop_match:
            expiry_date = go_shop_match.group(1)
            msg = f"Go-Shop period for {ticker} expires TODAY ({expiry_date})."
            save_reminder(event_id, ticker, expiry_date, msg)
            if funnel_metrics: 
                funnel_metrics[12] += 1

        if issuer_memory and issuer != "UNKNOWN":
            issuer_memory.add(issuer)

        return conclude(1, 'Alert', 'Alert Sent', 'Email Dispatched', issuer, event_family)

    return conclude(1, 'Rules Engine', 'Dropped', 'Failed Rules Threshold', issuer, 'Unknown')


def process_1_feed(rss_url, source_name, triage_all=False, country=None, language=None):
    print(f"\n[INGESTION] Polling RSS: {source_name} ({rss_url})")
    import requests
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
    try:
        articles = scraper.get_latest_articles(rss_url=rss_url)
    except Exception as e:
        print(f"[ERROR] Scraper {source_name} failed: {e}")
        return [], 0

    parsed_articles = []
    for i, article in enumerate(articles):
        article_key = f"{source_name}:{article['id']}"
        if article_exists(article_key):
            continue
        body = article.get("body", "")
        parsed_articles.append({
            "source_name": source_name,