"""
SSR 2.0: Ingestion Adapter
Dynamically fetches articles based on the active 'Sources' configuration in The Brain.
"""
import logging
import concurrent.futures
import time
import feedparser
import requests
from bs4 import BeautifulSoup
from src.sheets import batch_update_last_checked, batch_update_source_telemetry
from src.config.settings import SHEET_URL

logger = logging.getLogger(__name__)

from src.scrapers import get_scraper_for_source
from src.ingestion.checkpoints import get_checkpoint, set_checkpoint

def _fetch_rss_channel(source: dict) -> tuple:
    import time
    start_time = time.time()
    articles = []
    source_name = source.get("Source Name", source.get("Source", "Unknown"))
    url = source.get("Target URL", source.get("URL", ""))
    
    configured_mode = source.get("Type", "Unknown")
    # For generic RSS, mode is RSS
    config_drift = configured_mode.upper() not in ("RSS", "RSS PARSING")
    
    ledger = {
        "source": source_name,
        "configured_mode": configured_mode,
        "configured_url": url,
        "resolved_adapter": "Generic_RSS",
        "actual_mode": "RSS",
        "actual_url": url,
        "checkpoint_before": None,
        "checkpoint_found": False,
        "recovery_attempted": False,
        "recovery_status": "NOT_REQUIRED",
        "pages_scanned": 1,
        "articles_scanned": 0,
        "articles_emitted": 0,
        "oldest_article_seen": None,
        "newest_article_seen": None,
        "checkpoint_after": None,
        "config_drift": config_drift,
        "health": "OK",
        "reason": "",
        "potential_recall_loss": False,
        "checkpoint_frozen": False,
        "status": "OK", 
        "duration_sec": 0.0
    }
    
    if config_drift:
        logger.warning(f"[INGESTION] SOURCE_CONFIG_DRIFT: {source_name} configured as {configured_mode} but executed as RSS")
    
    if not url:
        ledger["status"] = "EMPTY"
        ledger["health"] = "DEGRADED"
        ledger["reason"] = "No URL provided"
        ledger["duration_sec"] = round(time.time() - start_time, 2)
        return articles, ledger, source_name
        
    try:
        feed = feedparser.parse(url)
        checkpoint = get_checkpoint(source_name, "RSS")
        ledger["checkpoint_before"] = checkpoint
        checkpoint_found = False
        
        if feed.entries:
            ledger["articles_scanned"] = len(feed.entries)
            ledger["oldest_article_seen"] = feed.entries[-1].get("link", url)
            ledger["newest_article_seen"] = feed.entries[0].get("link", url)
            
            for entry in feed.entries:
                link = entry.get("link", url)
                if checkpoint and link == checkpoint:
                    checkpoint_found = True
                    break
                    
                body_text = entry.get("summary", entry.get("description", ""))
                if "<" in body_text and ">" in body_text:
                    body_text = BeautifulSoup(body_text, "html.parser").get_text(separator=" ")
                    
                articles.append({
                    "source": source_name,
                    "channel": "RSS",
                    "title": entry.get("title", "No Title"),
                    "url": link,
                    "published": getattr(entry, "published", ""),
                    "body": body_text,
                    "article_hash": "",
                    "document_type": source.get("Type", "Press Release")
                })
                
            ledger["articles_emitted"] = len(articles)
            ledger["checkpoint_found"] = checkpoint_found
            
            if articles:
                if not checkpoint or checkpoint_found:
                    ledger["recovery_status"] = "NOT_REQUIRED"
                else:
                    ledger["status"] = "GAP_DETECTED"
                    ledger["health"] = "DEGRADED"
                    ledger["reason"] = "CHECKPOINT_NOT_REACHED — BACKFILL REQUIRED"
                    ledger["recovery_status"] = "GAP_DETECTED"
                    ledger["potential_recall_loss"] = True
                    ledger["checkpoint_frozen"] = True
                    logger.warning(f"[INGESTION] {source_name} (RSS) hit feed limit without finding checkpoint. Backfill required.")
        
        if len(articles) == 0:
            ledger["status"] = "EMPTY"
            
    except Exception as e:
        logger.error(f"[INGESTION] RSS fetch failed for {source_name}: {e}")
        ledger["status"] = "FAILED"
        ledger["health"] = "DEGRADED"
        ledger["reason"] = str(e)
        ledger["recovery_status"] = "FAILED"
        ledger["checkpoint_frozen"] = True
        
    if ledger["status"] in ("OK", "EMPTY") and articles and ledger["recovery_status"] in ("NOT_REQUIRED", "RECOVERED") and not ledger["checkpoint_frozen"]:
        set_checkpoint(source_name, "RSS", articles[0]["url"])
        ledger["checkpoint_after"] = articles[0]["url"]
    else:
        ledger["checkpoint_after"] = ledger["checkpoint_before"]
        
    ledger["duration_sec"] = round(time.time() - start_time, 2)
    return articles, ledger, source_name

def _fetch_html_channel(source: dict) -> tuple:
    import time
    start_time = time.time()
    articles = []
    source_name = source.get("Source Name", source.get("Source", "Unknown"))
    url = source.get("Target URL", source.get("URL", ""))
    configured_mode = source.get("Type", "Unknown")
    
    scraper = get_scraper_for_source(source_name)
    actual_adapter = scraper.__class__.__name__ if scraper else "Generic_HTML"
    
    ledger = {
        "source": source_name,
        "configured_mode": configured_mode,
        "configured_url": url,
        "resolved_adapter": actual_adapter,
        "actual_mode": "HTML",
        "actual_url": url,
        "checkpoint_before": None,
        "checkpoint_found": False,
        "recovery_attempted": False,
        "recovery_status": "NOT_REQUIRED",
        "pages_scanned": 1,
        "articles_scanned": 0,
        "articles_emitted": 0,
        "oldest_article_seen": None,
        "newest_article_seen": None,
        "checkpoint_after": None,
        "config_drift": False,
        "health": "OK",
        "reason": "",
        "potential_recall_loss": False,
        "checkpoint_frozen": False,
        "status": "OK", 
        "duration_sec": 0.0,
        "metadata": {} 
    }
    
    if not url:
        ledger["status"] = "EMPTY"
        ledger["health"] = "DEGRADED"
        ledger["reason"] = "No URL provided"
        ledger["duration_sec"] = round(time.time() - start_time, 2)
        return articles, ledger, source_name
        
    if scraper:
        try:
            logger.info(f"[INGESTION] Using dedicated scraper for '{source_name}'")
            checkpoint = get_checkpoint(source_name, "HTML")
            ledger["checkpoint_before"] = checkpoint
            
            max_pages = source.get("max_backfill_pages", 20)
            raw_articles = scraper.get_latest_articles(url=url, checkpoint=checkpoint, max_pages=max_pages)
            
            if hasattr(scraper, "scrape_metadata"):
                meta = scraper.scrape_metadata
                ledger["metadata"] = meta
                ledger["actual_mode"] = meta.get("mode", "HTML")
                ledger["recovery_status"] = meta.get("recovery_status", "NOT_REQUIRED")
                ledger["checkpoint_found"] = meta.get("checkpoint_found", False)
                ledger["pages_scanned"] = meta.get("pages_scanned", 1)
                ledger["articles_scanned"] = meta.get("articles_scanned", len(raw_articles))
                ledger["oldest_article_seen"] = meta.get("oldest_article_seen")
                ledger["recovery_attempted"] = meta.get("recovery_attempted", False)
                if meta.get("actual_url"):
                    ledger["actual_url"] = meta.get("actual_url")
                    
            if raw_articles:
                ledger["newest_article_seen"] = raw_articles[0].get("url") or raw_articles[0].get("id")
                if not ledger["oldest_article_seen"]:
                    ledger["oldest_article_seen"] = raw_articles[-1].get("url") or raw_articles[-1].get("id")
            
            # Drift semantics fix: if a dedicated adapter is used, we trust its mode shifts (like PRN backfill).
            # We only flag URL drift for dedicated adapters.
            if ledger["actual_url"] != ledger["configured_url"] and not ledger["actual_url"].startswith(ledger["configured_url"]):
                ledger["config_drift"] = True
                logger.warning(f"[INGESTION] SOURCE_CONFIG_DRIFT: {source_name} requested {ledger['configured_url']} but fetched {ledger['actual_url']}")
            
            if raw_articles:
                if ledger["recovery_status"] == "GAP_DETECTED":
                    ledger["status"] = "GAP_DETECTED"
                    ledger["health"] = "DEGRADED"
                    ledger["reason"] = "CHECKPOINT_NOT_REACHED — BACKFILL REQUIRED"
                    ledger["potential_recall_loss"] = True
                    ledger["checkpoint_frozen"] = True
                    logger.warning(f"[INGESTION] {source_name} hit limit without finding checkpoint.")
                elif ledger["recovery_status"] == "BLOCKED":
                    ledger["status"] = "GAP_DETECTED"
                    ledger["health"] = "DEGRADED"
                    ledger["reason"] = "CHECKPOINT_NOT_REACHABLE"
                    ledger["potential_recall_loss"] = True
                    ledger["checkpoint_frozen"] = True
                    logger.warning(f"[INGESTION] SOURCE DEGRADED: {source_name} blocked by 403. Checkpoint frozen. Potential recall loss: YES.")
            
            for ra in raw_articles:
                body_text = ra.get("body", "")
                if not body_text or len(body_text) < 500:
                    try:
                        fetched_body = scraper.get_article_body(ra["url"])
                        if fetched_body:
                            body_text = fetched_body
                    except Exception as body_err:
                        logger.error(f"Failed to fetch full HTML body for {ra['url']}: {body_err}")
                        ledger["status"] = "FAILED"
                        ledger["health"] = "DEGRADED"
                        ledger["reason"] = f"Body fetch failed: {body_err}"
                        ledger["checkpoint_frozen"] = True
                        break # FATAL INGESTION ERROR
                        
                articles.append({
                    "source": source_name,
                    "channel": ledger["actual_mode"],
                    "title": ra.get("title", "No Title"),
                    "url": ra.get("url", url),
                    "published": ra.get("published", ""),
                    "body": body_text,
                    "article_hash": "",
                    "document_type": source.get("Type", "Press Release")
                })
            
            ledger["articles_emitted"] = len(articles)
            if len(articles) == 0 and ledger["status"] == "OK":
                ledger["status"] = "EMPTY"
                
            if ledger["status"] in ("OK", "EMPTY") and raw_articles and ledger["recovery_status"] in ("NOT_REQUIRED", "RECOVERED") and not ledger["checkpoint_frozen"]:
                if "checkpoints_to_set" in ledger.get("metadata", {}):
                    for src, chnl, val in ledger["metadata"]["checkpoints_to_set"]:
                        set_checkpoint(src, chnl, val)
                    ledger["checkpoint_after"] = "multiple"
                else:
                    set_checkpoint(source_name, "HTML", raw_articles[0].get("url") or raw_articles[0].get("id"))
                    ledger["checkpoint_after"] = raw_articles[0].get("url") or raw_articles[0].get("id")
            else:
                ledger["checkpoint_after"] = ledger["checkpoint_before"]
                
            ledger["duration_sec"] = round(time.time() - start_time, 2)
            return articles, ledger, source_name
        except Exception as e:
            logger.error(f"[INGESTION] Scraper for '{source_name}' failed: {e}")
            ledger["status"] = "FAILED"
            ledger["health"] = "DEGRADED"
            ledger["reason"] = str(e)
            ledger["recovery_status"] = "FAILED"
            ledger["checkpoint_frozen"] = True
            ledger["checkpoint_after"] = ledger["checkpoint_before"]
            ledger["duration_sec"] = round(time.time() - start_time, 2)
            return [], ledger, source_name
            
    # Generic HTML Fallback
    try:
        # Drift detector for generic
        if configured_mode.upper() != ledger["actual_mode"].upper() and configured_mode.upper() not in ("RSS PARSING", "HTML PARSING"):
            ledger["config_drift"] = True
            logger.warning(f"[INGESTION] SOURCE_CONFIG_DRIFT: {source_name} configured {configured_mode} but fell back to HTML.")
            
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        resp = requests.get(url, headers=headers, timeout=10)
        ledger["articles_scanned"] = 1 if resp.status_code == 200 else 0
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            articles.append({
                "source": source_name,
                "channel": "HTML",
                "title": soup.title.string if soup.title else "HTML Document",
                "url": url,
                "published": "",
                "body": soup.get_text(separator=" ", strip=True)[:8000],
                "article_hash": "",
                "document_type": source.get("Type", "HTML")
            })
            ledger["articles_emitted"] = 1
            ledger["newest_article_seen"] = url
            ledger["oldest_article_seen"] = url
        else:
            ledger["status"] = "FAILED"
            ledger["health"] = "DEGRADED"
            ledger["reason"] = f"HTTP {resp.status_code}"
            
        if len(articles) == 0 and ledger["status"] == "OK":
            ledger["status"] = "EMPTY"
            
    except Exception as e:
        logger.error(f"[INGESTION] Generic HTML fetch failed for {source_name}: {e}")
        ledger["status"] = "FAILED"
        ledger["health"] = "DEGRADED"
        ledger["reason"] = str(e)
        
    ledger["checkpoint_after"] = ledger["checkpoint_before"]
    ledger["duration_sec"] = round(time.time() - start_time, 2)
    return articles, ledger, source_name

def fetch_all_feeds(active_sources: list = None) -> tuple:
    articles = []
    ingestion_ledger = []
    
    if not active_sources:
        logger.warning("[INGESTION] No active sources provided by configuration manifest.")
        return articles, ingestion_ledger
        
    active_targets = [s for s in active_sources if str(s.get("Enabled", str(s.get("Active", "TRUE")))).upper() == "TRUE"]
    logger.info(f"[INGESTION] Booting concurrent multi-channel ingestion for {len(active_targets)} active sources...")
    
    successful_sources = set()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for source in active_targets:
            url = source.get("Target URL", source.get("URL", ""))
            if not url:
                continue
                
            from src.scrapers import get_scraper_for_source
            if get_scraper_for_source(source.get("Source")):
                futures.append(executor.submit(_fetch_html_channel, source))
            else:
                futures.append(executor.submit(_fetch_rss_channel, source))
                
        for future in concurrent.futures.as_completed(futures):
            try:
                arts, ledger, source_name = future.result()
                if arts:
                    articles.extend(arts)
                if ledger:
                    ingestion_ledger.append(ledger)
                if source_name and ledger and ledger.get("status") in ["OK", "EMPTY"]:
                    successful_sources.add(source_name)
            except Exception as e:
                logger.error(f"[INGESTION] Thread fetch failed: {e}")
                
    if successful_sources:
        try:
            batch_update_last_checked(SHEET_URL, list(successful_sources))
        except Exception as sheet_err:
            logger.debug(f"[INGESTION] Failed to batch update Last Checked: {sheet_err}")
            
    if ingestion_ledger:
        try:
            batch_update_source_telemetry(SHEET_URL, ingestion_ledger)
        except Exception as sheet_err:
            logger.debug(f"[INGESTION] Failed to push source telemetry: {sheet_err}")
            
    logger.info(f"[INGESTION] Download sequence complete. Downloaded {len(articles)} raw articles across all channels.")
    return articles, ingestion_ledger