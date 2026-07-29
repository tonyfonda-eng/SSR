import re
import feedparser
import time

from src.database import (
    initialise_database,
    article_exists,
    save_article,
    article_count,
)

from src.scrapers.prnewswire import download_article
from src.scrapers import get_scraper_for_source
from src.sheets import load_rules, load_sources, load_playbooks, append_to_research_queue, update_last_checked
from src.sheets import load_rules, load_sources, load_playbooks, append_to_research_queue, update_last_checked, load_global_exclusions
from src.rules_engine import evaluate
from src.ai import classify_event, execute_playbook
from src.alerts.email import send_alert

SHEET_URL = "https://docs.google.com/spreadsheets/d/1YDOyc8WReBei-7LKPLiXZtmOGCmoY7zuyTvyfMHeL4E/edit#gid=0"

def _process_article(source_name, article_id, title, url, published, body, rules, playbook_map, global_exclusions=None):
    if global_exclusions is None:
        global_exclusions = []
        
    article_key = f"{source_name}:{article_id}"
    if article_exists(article_key):
        return 0

    if not body:
        print(f"    [SKIP] Empty body for {title}")
        return 0
        
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
        pattern = r'\b(?:NYSE|NASDAQ|TSX|TSXV|LSE|ASX|OTC|NYSE\s+AMERICAN|AMEX)\s*:\s*[A-Z]+\b'
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
    matches = evaluate(body, rules, threshold=5)

    if matches:
        print("    [MATCH] High confidence event signals detected!")
        
        # Classification (Stage 2)
        event_family = classify_event(body, matches)
        print(f"    [AI CLASSIFICATION] {event_family}")

        if "false positive" in event_family.lower() or event_family.strip().lower() == "unknown":
            print("    [AI REJECTED] Article flagged as noise/false positive.")
            save_article(
                source=source_name,
                article_id=article_id,
                title=title,
                url=url,
                published=published,
                body=body,
            )
            return 1

        # Ticker Verification (Stage 3)
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
            
        if ticker != "UNKNOWN" and "MOCK AI" not in ticker:
            import yfinance as yf
            try:
                info = yf.Ticker(ticker).info
                exchange = info.get("exchange")
                if not exchange or exchange.strip() == "":
                    print(f"    [YFINANCE REJECTED] Ticker {ticker} is not publicly traded.")
                    save_article(
                        source=source_name,
                        article_id=article_id,
                        title=title,
                        url=url,
                        published=published,
                        body=body,
                    )
                    return 1
                print(f"    [YFINANCE VERIFIED] {ticker} trades on {exchange}")
            except Exception as e:
                print(f"    [YFINANCE WARNING] Could not verify ticker {ticker}: {e}")

        confidence = matches[0]["_Score"]
        research_summary = "Playbook not found."

        # Playbook & AI Research (Stage 3)
        if event_family in playbook_map:
            playbook_steps = playbook_map[event_family]
            if playbook_steps.strip():
                print(f"    [AI RESEARCH] Executing playbook...")
                research_summary = execute_playbook(body, playbook_steps)
                print(f"    [AI RESEARCH] Done.")
            else:
                research_summary = "No specific research questions defined for this playbook."
        
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
            evidence_log=matches[0].get("_Evidence", [])
        )

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


def process_rss_feed(rss_url, rules, playbook_map, source_name, global_exclusions=None):
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
            global_exclusions=global_exclusions
        )
        time.sleep(1) # respect API limits
        
    return new_articles, len(feed.entries)

def process_custom_scraper(scraper, rules, playbook_map, source_name, global_exclusions=None):
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
            global_exclusions=global_exclusions
        )
        time.sleep(1) # respect API limits

    return new_articles, len(articles)

def main():
    print("=== Special Situations Radar v1.0.0 ===")
    
    initialise_database()

    print("Loading rules, sources, playbooks, and exclusions from Google Sheets...")
    rules = load_rules(SHEET_URL)
    sources = load_sources(SHEET_URL)
    playbooks = load_playbooks(SHEET_URL)
    global_exclusions = load_global_exclusions(SHEET_URL)

    playbook_map = {p['Playbook']: p.get('Questions/Research Steps', '') for p in playbooks}

    print(f"[LOADED] {len(sources)} Sources | {len(rules)} Rules | {len(playbooks)} Playbooks")

    total_new = 0
    source_stats = {}

    # Pipeline: Sources -> Articles
    for source in sources:
        is_enabled = str(source.get("Enabled", "")).upper() == "TRUE"
        source_name = source.get("Source", "Unknown")
        rss_url = source.get("RSS URL", "")
        
        if is_enabled:
            scraper = get_scraper_for_source(source_name)
            method_used = None
            
            # 1. Attempt HTML Custom Scraper First
            if scraper:
                try:
                    new_count, parsed_count = process_custom_scraper(scraper, rules, playbook_map, source_name, global_exclusions)
                    if parsed_count > 0:
                        method_used = "HTML"
                        total_new += new_count
                        source_stats[source_name] = {"count": parsed_count, "method": method_used}
                except Exception as e:
                    print(f"[WARNING] HTML Scraper failed for {source_name}: {e}. Falling back to RSS if available...")

            # 2. Fallback to RSS if HTML failed, returned 0, or didn't exist
            if not method_used and rss_url:
                try:
                    new_count, parsed_count = process_rss_feed(rss_url, rules, playbook_map, source_name, global_exclusions)
                    method_used = "RSS"
                    total_new += new_count
                    source_stats[source_name] = {"count": parsed_count, "method": method_used}
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
