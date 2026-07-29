import feedparser
import time

from src.database import (
    initialise_database,
    article_exists,
    save_article,
    article_count,
)

from src.prnewswire_parser import download_article
from src.sheets import load_rules, load_sources, load_playbooks, append_to_research_queue
from src.rules_engine import evaluate
from src.ai import classify_event, execute_playbook
from src.alerts.email import send_alert

SHEET_URL = "https://docs.google.com/spreadsheets/d/1YDOyc8WReBei-7LKPLiXZtmOGCmoY7zuyTvyfMHeL4E/edit#gid=0"

def process_rss_feed(source_url, rules, playbook_map, source_name):
    print(f"\n[INGESTION] Polling RSS: {source_name} ({source_url})")
    try:
        feed = feedparser.parse(source_url)
    except Exception as e:
        print(f"[ERROR] Failed to parse feed {source_url}: {e}")
        return 0

    new_articles = 0

    for entry in feed.entries:
        # Generate a unique key for the database
        article_id = entry.link.rstrip("/").split("-")[-1].replace(".html", "")
        article_key = f"{source_name}:{article_id}"

        # In production, we'd skip if it exists
        if article_exists(article_key):
            continue

        print(f"  [ARTICLE] {entry.title}")

        # Fallback cascade: try to scrape HTML, then use RSS summary
        body = download_article(entry.link)
        if not body:
            body = getattr(entry, "summary", getattr(entry, "description", ""))

        if not body:
            print("    [WARNING] No content extracted.")
            continue

        # Cash Event Detection (Stage 1)
        matches = evaluate(body, rules, threshold=15)

        if matches:
            print("    [MATCH] High confidence event signals detected!")
            
            # Classification (Stage 2)
            event_family = classify_event(body, matches)
            print(f"    [AI CLASSIFICATION] {event_family}")

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
                article_title=entry.title,
                article_url=entry.link,
                event_family=event_family,
                confidence=confidence
            )

            # Alerts
            send_alert(
                article_title=entry.title,
                article_url=entry.link,
                event_family=event_family,
                confidence=confidence,
                research_summary=research_summary
            )

        # Archive
        save_article(
            source=source_name,
            article_id=article_id,
            title=entry.title,
            url=entry.link,
            published=getattr(entry, "published", ""),
            body=body,
        )

        new_articles += 1
        time.sleep(1) # respect API limits
        
    return new_articles

def main():
    print("=== Special Situations Radar v1.0.0 ===")
    
    initialise_database()

    print("[LOADING] Fetching Control Centre from Google Sheets...")
    sources = load_sources(SHEET_URL)
    rules = load_rules(SHEET_URL)
    playbooks = load_playbooks(SHEET_URL)

    playbook_map = {p['Playbook']: p.get('Questions/Research Steps', '') for p in playbooks}

    print(f"[LOADED] {len(sources)} Sources | {len(rules)} Rules | {len(playbooks)} Playbooks")

    total_new = 0

    # Pipeline: Sources -> Articles
    for source in sources:
        is_enabled = str(source.get("Enabled", "")).upper() == "TRUE"
        source_name = source.get("Source", "Unknown")
        rss_url = source.get("RSS URL", "")
        
        if is_enabled:
            # We currently only support RSS ingestion natively in monitor
            if rss_url:
                total_new += process_rss_feed(rss_url, rules, playbook_map, source_name)
            else:
                # If HTML is newer/preferred, we'd need an HTML index scraper
                # The user's thread suggested checking HTML vs RSS. 
                # For this v1.0 release, we rely on the RSS URL if present.
                print(f"[SKIP] Source '{source_name}' enabled but missing RSS URL. HTML scrapers to be implemented.")
        
    print(f"\n[DATABASE] {total_new} new articles stored.")
    print(f"[DATABASE] Total articles: {article_count()}")

if __name__ == "__main__":
    main()
