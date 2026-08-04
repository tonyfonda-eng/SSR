"""
SSR 2.0: Ingestion Adapter
Dynamically fetches articles based on the active 'Sources' configuration in The Brain.
"""
import logging

logger = logging.getLogger(__name__)

def fetch_all_feeds(active_sources: list = None) -> list:
    """
    Scrapes feeds based on the dynamically injected sources config.
    """
    articles = []
    
    if not active_sources:
        logger.warning("[INGESTION] No active sources provided by configuration manifest.")
        return articles
        
    logger.info(f"[INGESTION] Booting ingestion sequence for {len(active_sources)} configured sources...")
    
    # Identify which sources are marked as 'Active' in the Google Sheet
    active_targets = [s for s in active_sources if str(s.get("Active", "TRUE")).upper() == "TRUE"]
    
    logger.info(f"[INGESTION] {len(active_targets)} sources are active.")
    
    # ---------------------------------------------------------------------
    # NOTE: In a live environment, this loop bridges to your actual 
    # RSS / HTTP scraping functions (e.g., feedparser, requests, playwright)
    # ---------------------------------------------------------------------
    for source in active_targets:
        source_name = source.get("Source Name", "Unknown")
        source_url = source.get("URL", "")
        # Try-catch block ensures one broken feed doesn't kill the whole ingestion
        try:
            # logger.info(f" -> Polling {source_name} ({source_url})")
            # MOCK IMPLEMENTATION - Replace with your actual scraper call:
            # scraped_data = my_legacy_scraper_function(source_url)
            # articles.extend(scraped_data)
            pass
        except Exception as e:
            logger.error(f"[INGESTION] Failed to poll {source_name}: {e}")
            
    return articles