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
from src.sheets import load_rules, load_sources, load_playbooks, append_to_research_queue, update_last_checked, load_global_exclusions, load_gold_standards
from src.rules_engine import evaluate
from src.rules_engine import evaluate
from src.ai import classify_event, execute_playbook, check_material_update
from src.alerts.email import send_alert
from src.options_calc import calculate_naked_call_roi

SHEET_URL = "https://docs.google.com/spreadsheets/d/1YDOyc8WReBei-7LKPLiXZtmOGCmoY7zuyTvyfMHeL4E/edit#gid=0"

def _process_article(source_name, article_id, title, url, published, body, rules, playbook_map, global_exclusions=None, gold_standards=None, triage_all=False, needs_translation=False):
    if global_exclusions is None:
        global_exclusions = []
        
    article_key = f"{source_name}:{article_id}"
    if article_exists(article_key):
        return 0

    if not body:
        print(f"    [SKIP] Empty body for {title}")
        return 0
        
    if needs_translation:
        print(f"    [TRANSLATION] Translating '{title}' to English...")
        from src.ai import translate_to_english
        title = translate_to_english(title)
        body = translate_to_english(body)
        
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
            
    # Regex Public Ticker Pre-Filter (Skip for EDGAR)
    if "edgar" not in source_name.lower():
        exchanges = (
            r"(NYSE|NASDAQ|OTC|OTCQX|OTCQB|AMEX|BATS|ARCA|NYSEMKT|TSX|TSXV|CSE|NEO|CBOE|"
            r"LSE|LON|FRA|ETR|XETRA|EPA|PAR|AMS|BRU|LIS|SWX|SIX|STO|CPH|HEL|OSL|VIE|MAD|BME|MIL|BIT|WSE|PRA|EURONEXT|"
            r"ASX|NZX|TYO|TSE|HKEX|HKG|SHG|SHE|SZSE|SSE|SGX|KRX|KOSPI|KOSDAQ|TWSE|TPE|BOM|BSE|NSE|"
            r"JSE|TASE|DFM|ADX|BOVESPA|B3|BMV|BCS)"
        )
        pattern = r'\b' + exchanges + r'(?:\s+[-A-Z]+)?\s*:\s*[A-Z0-9\.]+\b'
        matches = re.findall(pattern, body, re.IGNORECASE)
        if len(matches) == 0:
            print(f"    [REGEX REJECTED] No public tickers found. Likely a private company or noise.")
            save_article(
                source=source_name,
                article_id=article_id,
                title=title,
                url=url,
                published=published,
                body=body,
            )
            return 1
            
    print(f"  -> Processing: {title}")

    # Cash Event Detection (Stage 1)
    matches = evaluate(body, rules, threshold=10)

    if matches:
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

        if "false positive" in event_family.lower() or event_family.strip().lower() == "unknown":
            print("    [AI REJECTED] Article flagged as noise/false positive or failed quantitative filters.")
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
            
        is_update = False
        if ticker != "UNKNOWN" and "MOCK AI" not in ticker:
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
        gold_standard = gold_standards.get(event_family) if gold_standards else None
        print(f"    [AI RESEARCH] Generating Investment Memo...")
        research_summary = execute_playbook(body, playbook_steps, event_family, gold_standard, market_data_str=market_data_str)
        print(f"    [AI RESEARCH] Done.")
        
        # Log to Database
        log_research(event_id, article_id, confidence, research_summary)
        
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

        # Check for Go-Shop Expiry
        go_shop_match = re.search(r'GO-SHOP EXPIRY:\s*(\d{4}-\d{2}-\d{2})', research_summary)
        if go_shop_match:
            expiry_date = go_shop_match.group(1)
            msg = f"Go-Shop period for {ticker} ({event_family}) expires TODAY ({expiry_date}). Please review for any competing bids!"
            save_reminder(event_id, ticker, expiry_date, msg)
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


def process_rss_feed(rss_url, rules, playbook_map, source_name, global_exclusions=None, gold_standards=None, triage_all=False, needs_translation=False):
    print(f"\n[INGESTION] Polling RSS: {source_name} ({rss_url})")
    try:
        feed = feedparser.parse(rss_url)
    except Exception as e:
        print(f"[ERROR] Failed to parse feed {rss_url}: {e}")
        return 0

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
            needs_translation=needs_translation
        )
        time.sleep(1) # respect API limits
        
    return new_articles, len(feed.entries)

def process_custom_scraper(scraper, rules, playbook_map, source_name, global_exclusions=None, gold_standards=None, triage_all=False, needs_translation=False):
    print(f"\n[INGESTION] Polling Custom Scraper: {source_name}")
    try:
        articles = scraper.get_latest_articles()
    except Exception as e:
        print(f"[ERROR] Scraper {source_name} failed: {e}")
        return 0

    new_articles = 0

    for article in articles:
        # Check if exists before scraping body to save time/bandwidth
        article_key = f"{source_name}:{article['id']}"
        if article_exists(article_key):
            continue

        body = article.get("body")
        if not body:
            body = scraper.get_article_body(article['url'])
            
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
            needs_translation=needs_translation
        )
        time.sleep(1) # respect API limits

    return new_articles, len(articles)

def main():
    print("=== Special Situations Radar v1.0.0 ===")
    
    initialise_database()

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
                    new_count, parsed_count = process_custom_scraper(scraper, rules, playbook_map, source_name, global_exclusions, gold_standards, triage_all, needs_translation)
                    if parsed_count > 0:
                        method_used = "HTML"
                        total_new += new_count
                        source_stats[source_name] = {"count": parsed_count, "new": new_count, "method": method_used}
                except Exception as e:
                    print(f"[WARNING] HTML Scraper failed for {source_name}: {e}. Falling back to RSS if available...")

            # 2. Fallback to RSS if HTML failed, returned 0, or didn't exist
            if not method_used and rss_url:
                try:
                    new_count, parsed_count = process_rss_feed(rss_url, rules, playbook_map, source_name, global_exclusions, gold_standards, triage_all, needs_translation)
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

if __name__ == "__main__":
    main()
