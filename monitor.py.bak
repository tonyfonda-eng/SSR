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
from src.sheets import load_rules, load_sources, load_playbooks, append_to_research_queue, update_last_checked, load_global_exclusions, load_gold_standards, log_unknown_event, update_pipeline_metrics, load_daily_memory, batch_append_daily_memory, prune_daily_memory, load_source_reliability, log_ontology_review
from src.rules_engine import evaluate
from src.ai import classify_event, execute_playbook, clients
from src.alerts.email import send_alert
from src.issuer import extract_issuing_company
from src.options_calc import calculate_naked_call_roi



# ---------------------------------------------------------------------------
# Daily Issuer Memory — fast in-memory dedup that persists across the pipeline
# ---------------------------------------------------------------------------
class IssuerMemory:
    """
    In-memory cache of all issuing companies processed today.
    Loaded from Google Sheets at startup.
    Grows during the run as valid alerts are generated, then flushed to Sheets.
    """
    def __init__(self):
        self._issuers = set()
        self._new_additions = list()

    def load_from_db(self):
        """Load all issuers from the Daily Memory Google Sheet tab."""
        issuers = load_daily_memory(SHEET_URL)
        self._issuers = set([str(k).lower() for k in issuers if k])
        print(f"[DAILY MEMORY] Loaded {len(self._issuers)} issuers from Google Sheets cache.")

    def is_duplicate(self, issuer):
        """Check if this exact issuer was already processed today."""
        if not issuer or issuer == "UNKNOWN":
            return False
        return issuer.lower() in self._issuers

    def add(self, issuer):
        """Register an issuer as processed and queue it for Google Sheets append."""
        if issuer and issuer != "UNKNOWN":
            key_lower = issuer.lower()
            if key_lower not in self._issuers:
                self._issuers.add(key_lower)
                self._new_additions.append(issuer)

    def flush_to_sheets(self):
        """Push all newly generated events to the Google Sheet tab."""
        if self._new_additions:
            batch_append_daily_memory(SHEET_URL, self._new_additions)
            self._new_additions.clear()

    @property
    def size(self):
        return len(self._issuers)

def _process_article(source_name, article_id, title, url, published, body, rules, playbook_map, global_exclusions=None, gold_standards=None, triage_all=False, funnel_metrics=None, issuer_memory=None, document_type=None, country=None, language=None, document_type_scores=None, ontology_stats=None, source_reliability_scores=None):
    import time
    start_time = time.perf_counter()
    from src.monitoring import MetricsCollector
    metrics = MetricsCollector.get_instance()
    metrics.daily["downloaded"] += 1
    metrics.source_stats[source_name]["downloaded"] += 1
    
    def conclude(ret_val, stage, final_status, drop_reason, issuer_name="Unknown", event_family="Unknown"):
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        metrics.log_article(article_id, source_name, url, title, country, language, document_type, issuer_name, event_family, stage, final_status, drop_reason, elapsed_ms)
        return ret_val

    if global_exclusions is None:
        global_exclusions = []
        
    article_key = f"{source_name}:{article_id}"
    
    # 1. Check persistent SQLite dedup
    if article_exists(article_key):
        return conclude(0, 'Database', 'Dropped', 'Duplicate Article')

    if not body:
        print(f"    [SKIP] Empty body for {title}")
        if funnel_metrics: funnel_metrics[3] += 1
        return conclude(0, 'Download', 'Dropped', 'Empty Body')

    if funnel_metrics: funnel_metrics[2] += 1
    
    # 2. Extract Issuer and Dedupe
    issuer = extract_issuing_company(source_name, title, body)
    if issuer == "EXHAUSTED":
        print("    [CRITICAL] AI Providers are exhausted. Aborting ingestion loop to prevent spam and save cache.")
        return conclude("ABORT", 'Issuer Extraction', 'Dropped', 'AI Exhausted')
    if issuer_memory and issuer_memory.is_duplicate(issuer):
        print(f"    [DAILY MEMORY] Issuer '{issuer}' already processed today. Dropping duplicate syndicated news.")
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
        if re.search(r'\b' + re.escape(ex_lower) + r'\b', title_lower) or re.search(r'\b' + re.escape(ex_lower) + r'\b', body_lower):
            print(f"    [GLOBAL EXCLUSION] Match found for '{ex}'. Skipping article.")
            # Save it so we don't scan it again
            save_article(
                source=source_name,
                article_id=article_id,
                title=title,
                url=url,
                published=published,
                body=body,
            )
            return conclude(1, 'Global Exclusions', 'Dropped', 'Regex Failed', issuer)
            
    if funnel_metrics: funnel_metrics[4] += 1
    print(f"  -> Processing: {title}")

    # Cash Event Detection (Stage 1) — Language-Agnostic Ontology Extraction
    from src.ontology import extract_concepts, extract_statuses, get_all_matched_terms
    
    raw_text = f"{title}\n\n{body}"
    
    # Every article worldwide goes through the same ontology extraction
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
        
        # Continuous Learning: Log ALL non-US articles to Ontology Review
        if country and country.lower() not in ("us", "usa", "united states"):
            try:
                raw_terms = get_all_matched_terms(raw_text)
                concept_ids = [cid for cid, _ in ontology_concepts]
                log_ontology_review(SHEET_URL, country, source_name, language, document_type, raw_terms, title, url, concept_ids)
            except Exception as e:
                print(f"    [WARNING] Ontology review logging failed: {e}")
                
    except Exception as e:
        print(f"    [WARNING] Ontology extraction failed: {e}")
        
    article_obj = {
        "raw_text": raw_text,
        "document_type": document_type
    }
    
    # Source Reliability channel
    source_rel = 0
    if source_reliability_scores:
        source_rel = source_reliability_scores.get(source_name, 0)
    
    matches = evaluate(article_obj, rules, document_type_scores if document_type_scores else {},
                        ontology_concepts=ontology_concepts, ontology_statuses=ontology_statuses,
                        source_reliability=source_rel, threshold=10)

    if matches:
        if funnel_metrics: funnel_metrics[5] += 1
        print("    [MATCH] High confidence event signals detected!")
        
        # Ticker Verification (Stage 2)
        from src.ai import extract_target_ticker
        ticker = extract_target_ticker(body)
        print(f"    [AI TICKER] {ticker}")

        # --- AI EXHAUSTION CIRCUIT BREAKER ---
        if "MOCK AI" in ticker or "ERROR" in ticker or ticker == "UNKNOWN" or ticker == "EXHAUSTED":
            print("    [CRITICAL] AI Providers are exhausted or unavailable. Aborting ingestion loop to prevent spam and save cache.")
            return conclude("ABORT", 'Rules Engine', 'Dropped', 'AI Exhausted', issuer)
            
        if ticker == "PRIVATE":
            print("    [AI REJECTED] Target is a private company.")
            save_article(
                source=source_name,
                article_id=article_id,
                title=title,
                url=url,
                published=published,
                body=body,
            )
            return conclude(1, 'AI Classification', 'Dropped', 'Private Company', ticker)
            
        if funnel_metrics: funnel_metrics[6] += 1
        
        options_available = False
        market_cap = None
        market_data_str = ""
        if ticker != "UNKNOWN" and "MOCK AI" not in ticker:
            try:
                import yfinance as yf
                # Handle basic ticker formatting for yfinance if needed, otherwise rely on AI's output
                yf_ticker = yf.Ticker(ticker)
                
                mc = yf_ticker.info.get('marketCap')
                if mc:
                    market_cap = mc
                    print(f"    [FINANCIALS] Market Cap: ${market_cap:,.2f}")
                    
                current_price = yf_ticker.info.get('currentPrice', yf_ticker.info.get('regularMarketPrice'))
                if current_price:
                    market_data_str += f"Current Share Price: ${current_price}\n\n"
                    
                options = yf_ticker.options
                if options and len(options) > 0:
                    options_available = True
                    print(f"    [OPTIONS] Options chain available. Earliest exp: {options[0]}")
                    market_data_str += f"Exchange-listed Options Available: YES\n"
                else:
                    print(f"    [OPTIONS] No options chain found for {ticker}.")
                    market_data_str += f"Exchange-listed Options Available: NO\n"
                    
            except Exception as e:
                print(f"    [WARNING] Failed to fetch financial data for {ticker}: {e}")

        # Classification (Stage 3)
        event_family = classify_event(body, matches, ticker=ticker, market_cap=market_cap)
        print(f"    [AI CLASSIFICATION] {event_family}")
        
        if "Unknown" in event_family or event_family == "EXHAUSTED":
             print("    [CRITICAL] AI Providers are exhausted. Aborting ingestion loop.")
             return conclude("ABORT", 'AI Classification', 'Dropped', 'AI Exhausted', ticker, event_family)

        if "false positive" in event_family.lower():
            print("    [AI REJECTED] Article flagged as false positive.")
            if triage_all:
                print(f"    [BYPASS] Source '{source_name}' has Triage All enabled. Bypassing rejection for analysis.")
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
            print("    [UNKNOWN EVENT] Logging to Knowledge Base for review (Principle #6).")
            log_unknown_event(
                sheet_url=SHEET_URL,
                source=source_name,
                article_title=title,
                article_url=url,
                rules_score=matches[0]["_Score"],
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
            print(f"    [AI REJECTED] Strategy requires tradable options, but none found for {ticker}.")
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
            print(f"    [T12 METRICS] Calculating structural floor for {ticker} (Halt Date: {halt_date_str})...")
            
            # Using current_price as proxy for pre-halt price if yfinance has it cached, else None
            pre_halt = None
            if ticker != "UNKNOWN":
                try:
                    import yfinance as yf
                    pre_halt = yf.Ticker(ticker).info.get('previousClose')
                except:
                    pass
                    
            t12_data = get_t12_metrics(ticker, pre_halt_price=pre_halt, halt_date_str=halt_date_str)
            
            if not t12_data['valid']:
                print(f"    [T12 REJECTED] {t12_data.get('reason')}")
                save_article(
                    source=source_name, article_id=article_id, title=title,
                    url=url, published=published, body=body
                )
                return conclude(1, 'Playbook', 'Dropped', 'T12 Structural Floor Failed', ticker, event_family)
                
            print(f"    [T12 APPROVED] Net Cash/Share: ${t12_data['net_cash_per_share']:.2f} | Shares: {t12_data['shares_outstanding']:,} | Short: {t12_data['short_percent_of_float']*100:.1f}%")
            
            # Format market_data_str specifically for T12
            market_data_str = f"Net Cash Per Share (Discounted for {t12_data['halt_duration_days']} days halted): ${t12_data['net_cash_per_share']:.2f}\n"
            market_data_str += f"Total Shares Outstanding: {t12_data['shares_outstanding']:,}\n"
            market_data_str += f"Short Percent of Float: {t12_data['short_percent_of_float']*100:.1f}%\n"
            market_data_str += f"Previous Close (Pre-halt): ${t12_data['reference_price']}\n"
            if t12_data['gap_down_target_50'] > 0:
                market_data_str += f"50% Gap Down Target: ${t12_data['gap_down_target_50']:.2f}\n"
                market_data_str += f"70% Gap Down Target: ${t12_data['gap_down_target_70']:.2f}\n"
            market_data_str += "STRUCTURAL FLOOR VALIDATED: Gap down targets hit or breach Net Cash per share.\n\n"

        if funnel_metrics: funnel_metrics[7] += 1
        
        is_update = False
        if ticker != "UNKNOWN" and "MOCK AI" not in ticker:
            if funnel_metrics and options_available: funnel_metrics[8] += 1
            print(f"    [AI TICKER VERIFIED] Public ticker extracted: {ticker}")
            track_company(ticker)
            event_id, is_new = create_event_if_new(event_family, ticker)
            
            if not is_new:
                print(f"    [DEDUPLICATION] Event already tracked. Using Python heuristic to check for material updates...")
                
                # Pure Python heuristic for material updates
                material_keywords = ["bump", "increase", "amend", "terminate", "cancel", "revised", "superior proposal", "competing", "regulatory approval", "blocked"]
                body_lower = body.lower()
                title_lower = title.lower()
                
                is_material = any(kw in body_lower or kw in title_lower for kw in material_keywords)
                
                if is_material:
                    print(f"    [PYTHON UPDATE] Material update keywords detected. Generating new memo.")
                    is_update = True
                else:
                    print(f"    [PYTHON UPDATE] No material keywords found (Syndicated News/Duplicate). Dropping article.")
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
            
        confidence = matches[0]["_Score"]
        research_summary = "Playbook not found."

        playbook_steps = playbook_map.get(event_family, "")
        if event_family == "Resumption of Trading":
            playbook_steps += "\nCRITICAL T12 INSTRUCTIONS: You MUST answer the following in the memo: Why did the halt occur? How long did it last? Why was it lifted? Does anything look fishy? Is the stock expected to gap down?"
            
        gold_standard = gold_standards.get(event_family) if gold_standards else None
        print(f"    [AI RESEARCH] Generating Investment Memo...")
        research_summary = execute_playbook(body, playbook_steps, event_family, gold_standard, market_data_str=market_data_str)
        print(f"    [AI RESEARCH] Done.")
        
        if funnel_metrics and is_update: funnel_metrics[9] += 1
        
        # Log to Database
        log_research(event_id, article_id, confidence, research_summary)
        
        if funnel_metrics: funnel_metrics[10] += 1
        
        # Review (Sheets)
        append_to_research_queue(
            sheet_url=SHEET_URL,
            article_title=title,
            article_url=url,
            event_family=event_family,
            confidence=confidence
        )

    # Archive FIRST (commit point) — prevents infinite re-send loops if script crashes after email
    save_article(
        source=source_name,
        article_id=article_id,
        title=title,
        url=url,
        published=published,
        body=body,
    )

    if matches:
        # Alerts (safe to fail — article is already archived so it won't be re-processed)
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
            if funnel_metrics: funnel_metrics[11] += 1
            
        except Exception as e:
            print(f"    [ALERT ERROR] Failed to send email alert: {e}")

        # Check for Go-Shop Expiry
        go_shop_match = re.search(r'GO-SHOP EXPIRY:\s*(\d{4}-\d{2}-\d{2})', research_summary)
        if go_shop_match:
            expiry_date = go_shop_match.group(1)
            msg = f"Go-Shop period for {ticker} ({event_family}) expires TODAY ({expiry_date}). Please review for any competing bids!"
            save_reminder(event_id, ticker, expiry_date, msg)
            if funnel_metrics: funnel_metrics[12] += 1
            print(f"    [REMINDER] Saved go-shop expiry reminder for {expiry_date}")
            
        # Add to Daily Memory AFTER successful alert dispatch
        if issuer_memory and issuer != "UNKNOWN":
            issuer_memory.add(issuer)

    return conclude(1, 'Alert', 'Alert Sent', 'Email Dispatched', issuer, event_family)


def process_rss_feed(rss_url, source_name, triage_all=False, country=None, language=None):
    print(f"\n[INGESTION] Polling RSS: {source_name} ({rss_url})")
    try:
        # Use requests with a timeout to prevent feedparser from hanging indefinitely
        import requests
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(rss_url, headers=headers, timeout=15)
            response.raise_for_status()
            feed = feedparser.parse(response.content)
        except Exception as e:
            print(f"    [WARNING] RSS fetch failed for {rss_url}: {e}")
            return [], 0
    except Exception as e:
        print(f"[ERROR] Failed to parse feed {rss_url}: {e}")
        return [], 0

    parsed_articles = []

    for entry in feed.entries:
        article_id = entry.link.rstrip("/").split("-")[-1].replace(".html", "")
        
        article_key = f"{source_name}:{article_id}"
        if article_exists(article_key):
            continue
            
        # Fallback cascade: try to scrape HTML, then use RSS summary
        body = download_article(entry.link)
        if not body:
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
        time.sleep(1) # respect API limits
        
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
        if (i + 1) % 50 == 0:
            print(f"    [PROGRESS] Processed {i + 1}/{len(articles)} articles...")
            
        # Check if exists before scraping body to save time/bandwidth
        article_key = f"{source_name}:{article['id']}"
        if article_exists(article_key):
            continue

        body = article.get("body")
        if not body:
            try:
                body = scraper.get_article_body(article['url'])
            except Exception as e:
                print(f"[WARNING] Failed to fetch body for {article['url']}: {e}")
                body = None
            
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
        time.sleep(1) # respect API limits

    return parsed_articles, len(articles)

def cluster_articles(articles):
    """
    Groups identical syndicated articles across different providers.
    """
    clusters = []
    for article in articles:
        if not article.get('body'):
            continue
            
        found_cluster = False
        for cluster in clusters:
            rep = cluster[0]
            # Match titles (ignore case)
            similarity = SequenceMatcher(None, article['title'].lower(), rep['title'].lower()).ratio()
            
            if similarity > 0.8:
                cluster.append(article)
                found_cluster = True
                break
                
        if not found_cluster:
            clusters.append([article])
            
    # For each cluster, sort by body length descending so the richest text is index 0
    for cluster in clusters:
        cluster.sort(key=lambda x: len(x.get('body', '')), reverse=True)
        
    return clusters

def main():
    print("=== Special Situations Radar v1.0.0 ===")
    
    from src.monitoring import MetricsCollector
    metrics = MetricsCollector.get_instance()
    metrics.reset()
    
    initialise_database()
    
    # Build the daily issuer memory — loaded from DB, grows during this run
    issuer_memory = IssuerMemory()
    issuer_memory.load_from_db()
    
    funnel_metrics = {i: 0 for i in range(1, 13)}

    # Process pending reminders
    pending = get_pending_reminders()
    for rem in pending:
        print(f"[REMINDER] Sending scheduled alert for {rem['event_id']}")
        
        # Calculate fresh Naked Call ROI for the reminder
        roi_table = ""
        if rem.get('ticker') and rem['ticker'] != 'UNKNOWN':
            print(f"    -> Calculating Naked Call ROI for {rem['ticker']}...")
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

    print("Loading rules, sources, playbooks, and exclusions from Google Sheets...")
    rules = load_rules(SHEET_URL)
    sources = load_sources(SHEET_URL)
    playbooks = load_playbooks(SHEET_URL)
    global_exclusions = load_global_exclusions(SHEET_URL)
    gold_standards = load_gold_standards(SHEET_URL)

    playbook_map = {p['Playbook']: p.get('Questions/Research Steps', '') for p in playbooks}

    print(f"[LOADED] {len(sources)} Sources | {len(rules)} Rules | {len(playbooks)} Playbooks")

    from src.sheets import load_document_type_scores
    document_type_scores = load_document_type_scores(SHEET_URL)
    source_reliability_scores = load_source_reliability(SHEET_URL)
    
    # Load ontology from Google Sheets (once at startup — all languages)
    from src.ontology import load_ontology
    load_ontology(SHEET_URL)
    
    ontology_stats = {"total": 0, "extracted": 0, "missed": 0}

    all_new_articles = []
    source_stats = {}

    # Pipeline Phase 1: Ingestion across all sources
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
            
            # 1. Attempt HTML Custom Scraper First
            if scraper:
                try:
                    parsed, parsed_count = process_custom_scraper(scraper, source_name, rss_url=rss_url, triage_all=triage_all, country=country, language=language)
                    if funnel_metrics: funnel_metrics[1] += parsed_count
                    if parsed_count > 0:
                        method_used = "HTML"
                        all_new_articles.extend(parsed)
                        source_stats[source_name] = {"count": parsed_count, "new": len(parsed), "method": method_used}
                except Exception as e:
                    print(f"[WARNING] HTML Scraper failed for {source_name}: {e}. Falling back to RSS if available...")

            # 2. Fallback to RSS if HTML failed, returned 0, or didn't exist
            if not method_used and rss_url:
                try:
                    parsed, parsed_count = process_rss_feed(rss_url, source_name, triage_all, country, language)
                    if funnel_metrics: funnel_metrics[1] += parsed_count
                    method_used = "RSS"
                    all_new_articles.extend(parsed)
                    source_stats[source_name] = {"count": parsed_count, "new": len(parsed), "method": method_used}
                except Exception as e:
                    print(f"[ERROR] RSS Ingestion failed for {source_name}: {e}")

            if not method_used and not rss_url and not scraper:
                print(f"[SKIP] Source '{source_name}' enabled but missing RSS URL and no custom scraper found.")
                
    # Pipeline Phase 2: Cross-Provider Clustering
    print(f"\n[DEDUPLICATION] Clustering {len(all_new_articles)} new articles across all sources...")
    clusters = cluster_articles(all_new_articles)
    print(f"[DEDUPLICATION] Reduced to {len(clusters)} unique events.")
    
    total_new = 0
    for cluster in clusters:
        primary = cluster[0]
        
        # Process the best representative article
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
            funnel_metrics=funnel_metrics,
            issuer_memory=issuer_memory,
            document_type=primary.get("document_type"),
            country=primary.get("country"),
            language=primary.get("language"),
            document_type_scores=document_type_scores,
            ontology_stats=ontology_stats,
            source_reliability_scores=source_reliability_scores
        )
        if res == "ABORT":
            print("\n[CRITICAL] Aborting ingestion loop entirely due to AI Exhaustion.")
            break
        total_new += res
        
        # Quietly archive the syndicated clones to prevent fetching them again
        for clone in cluster[1:]:
            save_article(
                source=clone["source_name"],
                article_id=clone["article_id"],
                title=clone["title"],
                url=clone["url"],
                published=clone["published"],
                body=clone["body"]
            )
            print(f"    [DEDUPLICATION] Quietly archived syndicated clone: {clone['title']} ({clone['source_name']})")

    # Final cleanup and stat saves
    print(f"[DATABASE] {sum(s['new'] for s in source_stats.values())} new unique articles processed.")
    print(f"[DATABASE] Total articles archived: {article_count()}")
    
    # Flush memory to sheets and prune old entries
    issuer_memory.flush_to_sheets()
    prune_daily_memory(SHEET_URL)
    
    import time
    metrics.daily["total_runtime_s"] = time.perf_counter() - metrics.workflow_start
    if metrics.daily["total_runtime_s"] > 240:
        metrics.daily["anomalies"].add(f"Runtime > 4 mins ({metrics.daily['total_runtime_s']:.1f}s)")
        
    print("[MONITORING] Writing operational statistics to Google Sheets...")
    from src.sheets import update_daily_statistics, append_ai_usage, update_source_statistics
    update_daily_statistics(SHEET_URL, metrics.daily)
    append_ai_usage(SHEET_URL, dict(metrics.ai_telemetry))
    update_source_statistics(SHEET_URL, dict(metrics.source_stats))
    
    print("[MONITORING] Generating HTML Dashboard...")
    from src.database import save_lifecycle_logs, prune_lifecycle_logs, get_recent_lifecycle_logs
    
    # Extract just the values from the dict mapping
    log_rows = []
    for art_id, trace in metrics.article_traces.items():
        log_rows.append((
            art_id, trace["timestamp"], trace["source"], trace["title"], trace["url"], 
            trace["country"], trace["language"], trace["document_type"], trace["issuer"], 
            trace["event_family"], trace["stage"], trace["final_status"], trace["drop_reason"], 
            trace["processing_time_ms"]
        ))
        
    save_lifecycle_logs(log_rows)
    prune_lifecycle_logs(days=14)
    logs = get_recent_lifecycle_logs()
    
    from src.html_generator import generate_dashboard_html
    generate_dashboard_html(logs, output_path="docs/index.html")
    
    print(f"[DAILY MEMORY] Session ended with {issuer_memory.size} issuers cached.")

    if source_stats:
        import datetime
        timestamp_str = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        update_last_checked(SHEET_URL, source_stats, timestamp_str)
        update_pipeline_metrics(SHEET_URL, funnel_metrics, timestamp_str)
        
    print("\n[ONTOLOGY STATISTICS]")
    print(f"Total Foreign Articles Evaluated: {ontology_stats['total']}")
    if ontology_stats['total'] > 0:
        coverage = (ontology_stats['extracted'] / ontology_stats['total']) * 100
        print(f"Concepts Extracted: {ontology_stats['extracted']}")
        print(f"Missed Extractions: {ontology_stats['missed']}")
        print(f"Ontology Coverage:  {coverage:.1f}%")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        print(f"\n[FATAL ERROR] {e}")
        traceback.print_exc()
        # Exit with 1 so GH Actions shows failure
        import sys
        sys.exit(1)
