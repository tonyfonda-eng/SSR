import re

with open('src/ingestion/scrapers.py', 'r') as f:
    content = f.read()

# Refactor _fetch_rss_channel
rss_pattern = re.compile(r'def _fetch_rss_channel\(source: dict\) -> tuple:.*?return articles, ledger, source_name', re.DOTALL)
rss_replacement = """def _fetch_rss_channel(source: dict) -> tuple:
    start_time = time.time()
    articles = []
    source_name = source.get("Source Name", source.get("Source", "Unknown"))
    url = source.get("Target URL", source.get("URL", ""))
    
    configured_mode = source.get("Type", "Unknown")
    config_drift = configured_mode.upper() not in ("RSS", "RSS PARSING")
    
    ledger = {
        "source": source_name,
        "configured_mode": configured_mode,
        "configured_url": url,
        "resolved_adapter": "Generic_RSS",
        "actual_mode": "RSS",
        "actual_url": url,
        "channel": "RSS",
        "status": "OK",
        "error_message": "",
        "raw_found": 0,
        "parsed_found": 0,
        "duration_sec": 0.0,
        "unique_found": 0,
        "checkpoint_before": None,
        "checkpoint_after": None,
        "checkpoint_found": False,
        "recovery_status": "NOT_REQUIRED",
        "config_drift": config_drift,
        "gap_detected": False
    }
    
    if config_drift:
        logger.warning(f"[INGESTION] SOURCE_CONFIG_DRIFT: {source_name} configured as {configured_mode} but executed as RSS")
    
    if not url:
        ledger["status"] = "EMPTY"
        ledger["error_message"] = "No URL provided"
        ledger["duration_sec"] = round(time.time() - start_time, 2)
        return articles, ledger, source_name
        
    try:
        feed = feedparser.parse(url)
        checkpoint = get_checkpoint(source_name, "RSS")
        ledger["checkpoint_before"] = checkpoint
        checkpoint_found = False
        
        if feed.entries:
            ledger["raw_found"] = len(feed.entries)
            for entry in feed.entries:
                link = entry.get("link", url)
                if checkpoint and link == checkpoint:
                    checkpoint_found = True
                    break
                    
                body_text = entry.get("summary", entry.get("description", ""))
                
                # Clean HTML tags out of RSS summaries if they exist
                if "<" in body_text and ">" in body_text:
                    body_text = BeautifulSoup(body_text, "html.parser").get_text(separator=" ")
                    
                articles.append({
                    "source": source_name,
                    "url": link,
                    "headline": entry.get("title", "No Title"),
                    "body": body_text,
                    "document_type": source.get("Type", "Press Release"),
                    "_ingestion_mode": "RSS"
                })
            ledger["parsed_found"] = len(articles)
            ledger["checkpoint_found"] = checkpoint_found
            
            if articles:
                if not checkpoint or checkpoint_found:
                    ledger["recovery_status"] = "NOT_REQUIRED"
                else:
                    ledger["status"] = "GAP_DETECTED"
                    ledger["gap_detected"] = True
                    ledger["error_message"] = "CHECKPOINT_NOT_REACHED — BACKFILL REQUIRED"
                    ledger["recovery_status"] = "GAP_DETECTED"
                    logger.warning(f"[INGESTION] {source_name} (RSS) hit feed limit without finding checkpoint. Backfill required.")
        
        if len(articles) == 0:
            ledger["status"] = "EMPTY"
            
    except Exception as e:
        logger.error(f"[INGESTION] RSS fetch failed for {source_name}: {e}")
        ledger["status"] = "ERROR"
        ledger["error_message"] = str(e)
        ledger["recovery_status"] = "FAILED"
        
    # Transactional checkpoint logic
    if ledger["status"] in ("OK", "EMPTY") and articles and ledger["recovery_status"] in ("NOT_REQUIRED", "RECOVERED"):
        set_checkpoint(source_name, "RSS", articles[0]["url"])
        ledger["checkpoint_after"] = articles[0]["url"]
        
    ledger["duration_sec"] = round(time.time() - start_time, 2)
    return articles, ledger, source_name"""

# Refactor _fetch_html_channel
html_pattern = re.compile(r'def _fetch_html_channel\(source: dict\) -> tuple:.*?return articles, ledger, source_name', re.DOTALL)
html_replacement = """def _fetch_html_channel(source: dict) -> tuple:
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
        "channel": "HTML",
        "status": "OK",
        "error_message": "",
        "raw_found": 0,
        "parsed_found": 0,
        "duration_sec": 0.0,
        "unique_found": 0,
        "checkpoint_before": None,
        "checkpoint_after": None,
        "checkpoint_found": False,
        "recovery_status": "NOT_REQUIRED",
        "config_drift": False,
        "gap_detected": False,
        "metadata": {}
    }
    
    if not url:
        ledger["status"] = "EMPTY"
        ledger["error_message"] = "No URL provided"
        ledger["duration_sec"] = round(time.time() - start_time, 2)
        return articles, ledger, source_name
        
    if scraper:
        try:
            logger.info(f"[INGESTION] Using dedicated scraper for '{source_name}'")
            checkpoint = get_checkpoint(source_name, "HTML")
            ledger["checkpoint_before"] = checkpoint
            
            # Allow configurable backfill limits
            max_pages = source.get("max_backfill_pages", 20)
            raw_articles = scraper.get_latest_articles(url=url, checkpoint=checkpoint, max_pages=max_pages)
            ledger["raw_found"] = len(raw_articles)
            
            if hasattr(scraper, "scrape_metadata"):
                meta = scraper.scrape_metadata
                ledger["metadata"] = meta
                ledger["actual_mode"] = meta.get("mode", "HTML")
                ledger["recovery_status"] = meta.get("recovery_status", "NOT_REQUIRED")
                ledger["checkpoint_found"] = meta.get("checkpoint_found", False)
                if meta.get("actual_url"):
                    ledger["actual_url"] = meta.get("actual_url")
                    
            if configured_mode.upper() != ledger["actual_mode"].upper() and configured_mode.upper() not in ("RSS PARSING", "HTML PARSING"):
                ledger["config_drift"] = True
                
            if ledger["actual_url"] != ledger["configured_url"] and not ledger["actual_url"].startswith(ledger["configured_url"]):
                ledger["config_drift"] = True
                
            if ledger["config_drift"]:
                logger.warning(f"[INGESTION] SOURCE_CONFIG_DRIFT: {source_name} configured mode/url doesn't match actual.")
            
            if raw_articles:
                if ledger["recovery_status"] == "GAP_DETECTED":
                    ledger["status"] = "GAP_DETECTED"
                    ledger["gap_detected"] = True
                    ledger["error_message"] = "CHECKPOINT_NOT_REACHED — BACKFILL REQUIRED"
                    logger.warning(f"[INGESTION] {source_name} hit limit without finding checkpoint.")
                elif ledger["recovery_status"] == "BLOCKED":
                    ledger["status"] = "GAP_DETECTED"
                    ledger["gap_detected"] = True
                    ledger["error_message"] = "CHECKPOINT_NOT_REACHABLE — BLOCKED_BY_403"
                    logger.warning(f"[INGESTION] SOURCE DEGRADED: {source_name} blocked by 403. Checkpoint frozen. Potential recall loss: YES.")
            
            for ra in raw_articles:
                body_text = ra.get("body", "")
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
                    "_ingestion_mode": ledger["actual_mode"]
                })
            
            ledger["parsed_found"] = len(articles)
            if len(articles) == 0:
                ledger["status"] = "EMPTY"
                
            # Transactional checkpoint logic
            if ledger["status"] in ("OK", "EMPTY") and raw_articles and ledger["recovery_status"] in ("NOT_REQUIRED", "RECOVERED"):
                set_checkpoint(source_name, "HTML", raw_articles[0].get("url") or raw_articles[0].get("id"))
                ledger["checkpoint_after"] = raw_articles[0].get("url") or raw_articles[0].get("id")
                
            ledger["duration_sec"] = round(time.time() - start_time, 2)
            return articles, ledger, source_name
        except Exception as e:
            logger.error(f"[INGESTION] Scraper for '{source_name}' failed: {e}")
            ledger["status"] = "TIMEOUT" if "timeout" in str(e).lower() else "ERROR"
            ledger["error_message"] = str(e)
            ledger["recovery_status"] = "FAILED"
            ledger["duration_sec"] = round(time.time() - start_time, 2)
            return [], ledger, source_name
            
    # Generic HTML Fallback
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        resp = requests.get(url, headers=headers, timeout=10)
        ledger["raw_found"] = 1 if resp.status_code == 200 else 0
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
            ledger["parsed_found"] = len(articles)
        else:
            ledger["status"] = "ERROR"
            ledger["error_message"] = f"HTTP {resp.status_code}"
            
        if len(articles) == 0 and ledger["status"] == "OK":
            ledger["status"] = "EMPTY"
            
    except Exception as e:
        logger.error(f"[INGESTION] Generic HTML fetch failed for {source_name}: {e}")
        ledger["status"] = "TIMEOUT" if "timeout" in str(e).lower() else "ERROR"
        ledger["error_message"] = str(e)
        
    ledger["duration_sec"] = round(time.time() - start_time, 2)
    return articles, ledger, source_name"""

content = rss_pattern.sub(rss_replacement, content)
content = html_pattern.sub(html_replacement, content)

with open('src/ingestion/scrapers.py', 'w') as f:
    f.write(content)
