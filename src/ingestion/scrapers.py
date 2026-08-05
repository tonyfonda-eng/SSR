"""
SSR 2.0: Ingestion Adapter
Dynamically fetches articles based on the active 'Sources' configuration in The Brain.
"""
import logging
import concurrent.futures
import feedparser
import requests
from bs4 import BeautifulSoup
from src.sheets import batch_update_last_checked
from src.config.settings import SHEET_URL

logger = logging.getLogger(__name__)

from src.scrapers import get_scraper_for_source

def _fetch_rss_channel(source: dict) -> tuple:
    articles = []
    source_name = source.get("Source Name", source.get("Source", "Unknown"))
    url = source.get("RSS URL", source.get("URL", ""))
    
    if not url:
        return articles, None
        
    try:
        feed = feedparser.parse(url)
        if feed.entries:
            for entry in feed.entries:
                body_text = entry.get("summary", entry.get("description", ""))
                
                # Clean HTML tags out of RSS summaries if they exist
                if "<" in body_text and ">" in body_text:
                    body_text = BeautifulSoup(body_text, "html.parser").get_text(separator=" ")
                    
                articles.append({
                    "source": source_name,
                    "url": entry.get("link", url),
                    "headline": entry.get("title", "No Title"),
                    "body": body_text,
                    "document_type": source.get("Type", "Press Release"),
                    "_ingestion_mode": "RSS"
                })
        return articles, source_name
    except Exception as e:
        logger.error(f"[INGESTION] RSS fetch failed for {source_name}: {e}")
        return [], None

def _fetch_html_channel(source: dict) -> tuple:
    articles = []
    source_name = source.get("Source Name", source.get("Source", "Unknown"))
    url = source.get("HTML URL", "")
    
    if not url:
        return articles, None
        
    scraper = get_scraper_for_source(source_name)
    if scraper:
        try:
            logger.info(f"[INGESTION] Using dedicated HTML scraper for '{source_name}'")
            raw_articles = scraper.get_latest_articles(url=url)
            for ra in raw_articles:
                body_text = ra.get("body", "")
                # If body is missing or very short, try to fetch the full text
                if not body_text or len(body_text) < 500:
                    try:
                        fetched_body = scraper.get_article_body(ra["url"])
                        if fetched_body:
                            body_text = fetched_body
                    except Exception as body_err:
                        logger.debug(f"Failed to fetch full HTML body for {ra['url']}: {body_err}")
                        
                articles.append({
                    "source": source_name,
                    "url": ra.get("url", url),
                    "headline": ra.get("title", "No Title"),
                    "body": body_text,
                    "document_type": source.get("Type", "Press Release"),
                    "_ingestion_mode": "HTML"
                })
            return articles, source_name
        except Exception as e:
            logger.error(f"[INGESTION] HTML scraper for '{source_name}' failed: {e}")
            return [], None
            
    # Generic HTML Fallback
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            articles.append({
                "source": source_name,
                "url": url,
                "headline": soup.title.string if soup.title else "HTML Document",
                "body": soup.get_text(separator=" ", strip=True)[:8000],
                "document_type": source.get("Type", "HTML"),
                "_ingestion_mode": "HTML"
            })
        return articles, source_name
    except Exception as e:
        logger.error(f"[INGESTION] Generic HTML fetch failed for {source_name}: {e}")
        return [], None


def fetch_all_feeds(active_sources: list = None) -> list:
    """
    Scrapes feeds concurrently based on the dynamically injected sources config.
    """
    articles = []
    
    if not active_sources:
        logger.warning("[INGESTION] No active sources provided by configuration manifest.")
        return articles
        
    active_targets = [s for s in active_sources if str(s.get("Enabled", str(s.get("Active", "TRUE")))).upper() == "TRUE"]
    logger.info(f"[INGESTION] Booting concurrent multi-channel ingestion for {len(active_targets)} active sources...")
    
    successful_sources = set()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for source in active_targets:
            # RSS collector
            if source.get("RSS URL") or source.get("URL"):
                futures.append(executor.submit(_fetch_rss_channel, source))
            
            # HTML collector
            if source.get("HTML URL"):
                futures.append(executor.submit(_fetch_html_channel, source))
                
        for future in concurrent.futures.as_completed(futures):
            try:
                arts, source_name = future.result()
                if arts:
                    articles.extend(arts)
                if source_name:
                    successful_sources.add(source_name)
            except Exception as e:
                logger.error(f"[INGESTION] Thread fetch failed: {e}")
                
    if successful_sources:
        try:
            batch_update_last_checked(SHEET_URL, list(successful_sources))
        except Exception as sheet_err:
            logger.debug(f"[INGESTION] Failed to batch update Last Checked: {sheet_err}")
            
    logger.info(f"[INGESTION] Download sequence complete. Downloaded {len(articles)} raw articles across all channels.")
    return articles