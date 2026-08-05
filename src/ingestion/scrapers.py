"""
SSR 2.0: Ingestion Adapter
Dynamically fetches articles based on the active 'Sources' configuration in The Brain.
"""
import logging
import feedparser
import requests
from bs4 import BeautifulSoup
from src.sheets import update_last_checked
from src.config.settings import SHEET_URL

logger = logging.getLogger(__name__)

def fetch_all_feeds(active_sources: list = None) -> list:
    """
    Scrapes feeds based on the dynamically injected sources config.
    """
    articles = []
    
    if not active_sources:
        logger.warning("[INGESTION] No active sources provided by configuration manifest.")
        return articles
        
    active_targets = [s for s in active_sources if str(s.get("Active", "TRUE")).upper() == "TRUE"]
    logger.info(f"[INGESTION] Booting ingestion sequence for {len(active_targets)} active sources...")
    
    for source in active_targets:
        source_name = source.get("Source Name", source.get("Source", "Unknown"))
        url = source.get("URL", source.get("HTML URL", ""))
        
        if not url:
            continue
            
        try:
            # 1. Parse as RSS (Primary Method)
            feed = feedparser.parse(url)
            if feed.entries:
                for entry in feed.entries[:25]:  # Fetch top 25 recent per source
                    body_text = entry.get("summary", entry.get("description", ""))
                    
                    # Clean HTML tags out of RSS summaries if they exist
                    if "<" in body_text and ">" in body_text:
                        body_text = BeautifulSoup(body_text, "html.parser").get_text(separator=" ")
                        
                    articles.append({
                        "source": source_name,
                        "url": entry.get("link", url),
                        "headline": entry.get("title", "No Title"),
                        "body": body_text,
                        "document_type": source.get("Type", "Press Release")
                    })
            else:
                # 2. Fallback: Parse as raw HTML if it's not an RSS feed
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
                resp = requests.get(url, headers=headers, timeout=10)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    articles.append({
                        "source": source_name,
                        "url": url,
                        "headline": soup.title.string if soup.title else "HTML Document",
                        "body": soup.get_text(separator=" ", strip=True)[:8000],
                        "document_type": source.get("Type", "HTML")
                    })
                    
            # 3. Ping Google Sheets to update Column K (Last Checked)
            try:
                update_last_checked(SHEET_URL, source_name)
            except Exception as sheet_err:
                logger.debug(f"Failed to update Last Checked for {source_name}: {sheet_err}")
                
        except Exception as e:
            logger.error(f"[INGESTION] Failed to poll {source_name}: {e}")
            
    logger.info(f"[INGESTION] Download sequence complete. Downloaded {len(articles)} raw articles.")
    return articles