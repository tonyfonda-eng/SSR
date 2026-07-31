import re
import feedparser
import time

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
from src.sheets import load_rules, load_sources, load_playbooks, append_to_research_queue, update_last_checked, load_global_exclusions, load_gold_standards, log_unknown_event, update_pipeline_metrics
from src.rules_engine import evaluate
from src.ai import classify_event, execute_playbook, check_material_update
from src.alerts.email import send_alert
from src.options_calc import calculate_naked_call_roi

SHEET_URL = "https://docs.google.com/spreadsheets/d/1YDOyc8WReBei-7LKPLiXZtmOGCmoY7zuyTvyfMHeL4E/edit#gid=0"

def _process_article(source_name, article_id, title, url, published, body, rules, playbook_map, global_exclusions=None, gold_standards=None, triage_all=False, needs_translation=False, funnel_metrics=None):
    if global_exclusions is None:
        global_exclusions = []
        
    article_key = f"{source_name}:{article_id}"
    if article_exists(article_key):
        return 0

    if not body:
        print(f"    [SKIP] Empty body for {title}")
        return 0
        
    if funnel_metrics: funnel_metrics[2] += 1
    
    if needs_translation:
        print(f"    [TRANSLATION] Translating '{title}' to English...")
        from src.ai import translate_to_english
        title = translate_to_english(title)
        body = translate_to_english(body)
        
    if funnel_metrics and needs_translation: funnel_metrics[3] += 1

        
    # Global Exclusion Pre-Filter
    title_lower = title.lower()
    body_lower = body.lower()
    for ex in global_exclusions:
        if ex in title_lower or ex in body_lower:
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
            return 1
            
    if funnel_metrics: funnel_metrics[4] += 1
    print(f"  -> Processing: {title}")

    # Cash Event Detection (Stage 1)
    matches = evaluate(body, rules, threshold=10)

    if matches:
        if funnel_metrics: funnel_metrics[5] += 1
        print("    [MATCH] High confidence event signals detected!")
        
        # Ticker Verification (Stage 2)
        from src.ai import extract_target_ticker
        ticker = extract_target_ticker(body)
        print(f"    [AI TICKER] {ticker}")
        
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
            return 1
            
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
                return 1
                
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
            return 1
            
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
            return 1
            
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
                return 1
                
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
                print(f"    [DEDUPLICATION] Event already tracked. Checking for material updates...")
                if check_material_update(body, event_family, ticker):
                    print(f"    [AI UPDATE] Material update detected. Generating new memo.")
                    is_update = True
                else:
                    print(f"    [AI UPDATE] No material update. Dropping syndicated noise.")
                    save_article(
                        source=source_name,
                        article_id=article_id,
                        title=title,
                        url=url,
                        published=published,
                        body=body,
                    )
                    return 1
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

        # Alerts
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

        # Check for Go-Shop Expiry
        go_shop_match = re.search(r'GO-SHOP EXPIRY:\s*(\d{4}-\d{2}-\d{2})', research_summary)
        if go_shop_match:
            expiry_date = go_shop_match.group(1)
            msg = f"Go-Shop period for {ticker} ({event_family}) expires TODAY ({expiry_date}). Please review for any competing bids!"
            save_reminder(event_id, ticker, expiry_date, msg)
            if funnel_metrics: funnel_metrics[12] += 1
            print(f"    [REMINDER] Saved go-shop expiry reminder for {expiry_date}")

    # Archive
    save_article(
        source=source_name,
        article_id=article_id,
        title=title,
        url=url,
        published=published,
        body=body,
    )
    return 1


def process_rss_feed(rss_url, rules, playbook_map, source_name, global_exclusions=None, gold_standards=None, triage_all=False, needs_translation=False, funnel_metrics=None):
    print(f"\n[INGESTION] Polling RSS: {source_name} ({rss_url})")
    try:
        feed = feedparser.parse(rss_url)
    except Exception as e:
        print(f"[ERROR] Failed to parse feed {rss_url}: {e}")
        return 0, 0

    new_articles = 0

    for entry in feed.entries:
        article_id = entry.link.rstrip("/").split("-")[-1].replace(".html", "")
        
        # Fallback cascade: try to scrape HTML, then use RSS summary
        body = download_article(entry.link)
        if not body:
            body = getattr(entry, "summary", getattr(entry, "description", ""))

        published = getattr(entry, "published", "")
        
        new_articles += _process_article(
            source_name=source_name, 
            article_id=article_id, 
            title=entry.title, 
            url=entry.link, 
            published=published, 
            body=body, 
            rules=rules, 
            playbook_map=playbook_map,
            global_exclusions=global_exclusions,
            gold_standards=gold_standards,
            triage_all=triage_all,
            needs_translation=needs_translation,
            funnel_metrics=funnel_metrics
        )
        time.sleep(1) # respect API limits
        
    return new_articles, len(feed.entries)

def process_custom_scraper(scraper, rules, playbook_map, source_name, global_exclusions=None, gold_standards=None, triage_all=False, needs_translation=False, funnel_metrics=None):
    print(f"\n[INGESTION] Polling Custom Scraper: {source_name}")
    try:
        articles = scraper.get_latest_articles()
    except Exception as e:
        print(f"[ERROR] Scraper {source_name} failed: {e}")
        return 0, 0

    new_articles = 0

    for article in articles:
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
            
        new_articles += _process_article(
            source_name=source_name, 
            article_id=article['id'], 
            title=article['title'], 
            url=article['url'], 
            published=article.get('published', ''), 
            body=body, 
            rules=rules, 
            playbook_map=playbook_map,
            global_exclusions=global_exclusions,
            gold_standards=gold_standards,
            triage_all=triage_all,
            needs_translation=needs_translation,
            funnel_metrics=funnel_metrics
        )
        time.sleep(1) # respect API limits

    return new_articles, len(articles)

def main():
    print("=== Special Situations Radar v1.0.0 ===")
    
    initialise_database()
    
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

    total_new = 0
    source_stats = {}

    # Pipeline: Sources -> Articles
    for source in sources:
        is_enabled = str(source.get("Enabled", "")).upper() == "TRUE"
        source_name = source.get("Source", "Unknown")
        rss_url = source.get("RSS URL", "")
        triage_all = str(source.get("Triage All (Email Rejections)", "")).strip().upper() == "TRUE"
        needs_translation = str(source.get("Needs Translation", "")).strip().upper() == "TRUE"
        
        if is_enabled:
            scraper = get_scraper_for_source(source_name)
            method_used = None
            
            # 1. Attempt HTML Custom Scraper First
            if scraper:
                try:
                    new_count, parsed_count = process_custom_scraper(scraper, rules, playbook_map, source_name, global_exclusions, gold_standards, triage_all, needs_translation, funnel_metrics)
                    if parsed_count > 0:
                        method_used = "HTML"
                        total_new += new_count
                        source_stats[source_name] = {"count": parsed_count, "new": new_count, "method": method_used}
                except Exception as e:
                    print(f"[WARNING] HTML Scraper failed for {source_name}: {e}. Falling back to RSS if available...")

            # 2. Fallback to RSS if HTML failed, returned 0, or didn't exist
            if not method_used and rss_url:
                try:
                    new_count, parsed_count = process_rss_feed(rss_url, rules, playbook_map, source_name, global_exclusions, gold_standards, triage_all, needs_translation, funnel_metrics)
                    method_used = "RSS"
                    total_new += new_count
                    source_stats[source_name] = {"count": parsed_count, "new": new_count, "method": method_used}
                except Exception as e:
                    print(f"[ERROR] RSS Ingestion failed for {source_name}: {e}")

            if not method_used and not rss_url and not scraper:
                print(f"[SKIP] Source '{source_name}' enabled but missing RSS URL and no custom scraper found.")
    print(f"\n[DATABASE] {total_new} new articles stored.")
    print(f"[DATABASE] Total articles: {article_count()}")

    import datetime
    timestamp_str = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    update_last_checked(SHEET_URL, source_stats, timestamp_str)
    update_pipeline_metrics(SHEET_URL, funnel_metrics, timestamp_str)

if __name__ == "__main__":
    main()
