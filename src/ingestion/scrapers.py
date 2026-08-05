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

def _fetch_single_source(source: dict) -> tuple:
    """Worker function to fetch a single source feed or HTML fallback."""
    articles = []
    source_name = source.get("Source Name", source.get("Source", "Unknown"))
    url = source.get("URL", source.get("HTML URL", ""))
    
    if not url:
        return articles, None
        
    try:
        # 1. Parse as RSS (Primary Method)
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
        else:
            # 2. Fallback: Parse as raw HTML if it's not an RSS feed
            logger.warning(f"[INGESTION] '{source_name}' has no valid RSS/Atom entries at {url} — "
                            f"falling back to raw HTML scrape. This will likely re-ingest the same "
                            f"static page every run. Check/update this source's URL in the Sheet.")
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
                    "_ingestion_mode": "HTML_FALLBACK"
                })
                
        return articles, source_name
    except Exception as e:
        logger.error(f"[INGESTION] Failed to poll {source_name}: {e}")
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
    
    # Also ensure we don't try to scrape completely blank sources
    active_targets = [s for s in active_targets if s.get("URL") or s.get("HTML URL")]
    
    logger.info(f"[INGESTION] Booting concurrent ingestion sequence for {len(active_targets)} active sources...")
    
    successful_sources = []
    
    # Use ThreadPoolExecutor to fetch all feeds in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_source = {executor.submit(_fetch_single_source, source): source for source in active_targets}
        for future in concurrent.futures.as_completed(future_to_source):
            try:
                arts, source_name = future.result()
                if arts:
                    articles.extend(arts)
                if source_name:
                    successful_sources.append(source_name)
            except Exception as e:
                logger.error(f"[INGESTION] Thread fetch failed: {e}")
                
    # Batch update Google Sheets to avoid API rate limits
    if successful_sources:
        try:
            batch_update_last_checked(SHEET_URL, successful_sources)
        except Exception as sheet_err:
            logger.debug(f"[INGESTION] Failed to batch update Last Checked: {sheet_err}")
            
    logger.info(f"[INGESTION] Download sequence complete. Downloaded {len(articles)} raw articles.")
    return articles