import feedparser
from curl_cffi import requests

from src.scrapers.base import SourceScraper
from src.config.settings import USER_AGENT

class PRNewsWireScraper(SourceScraper):
    """
    Optimized PR Newswire Scraper.
    Bypasses legacy HTML parsing in favor of the structured RSS data stream.
    """
    
    # Official RSS endpoint
    RSS_URL = "https://www.prnewswire.com/rss/news-releases-list.rss"
    
    def get_latest_articles(self, **kwargs):
        import time
        from bs4 import BeautifulSoup
        import feedparser
        
        base_url = "https://www.prnewswire.com/news-releases/news-releases-list/"
        checkpoint = kwargs.get("checkpoint")
        # Temporarily increased to 100 to catch up on overnight gap
        max_pages = kwargs.get("max_pages", 100)
        
        self.scrape_metadata = {
            "source": "PR Newswire",
            "mode": "RSS",
            "checkpoint_found": False,
            "recovery_attempted": False,
            "recovery_status": "NOT_REQUIRED",
            "pages_scanned": 0,
            "articles_recovered": 0,
            "pages_visited": 0,
            "page_limit": max_pages,
            "articles_scanned": 0,
            "oldest_article_seen": None,
            "emergency_stop": False,
            "reason": "",
            "last_checkpoint_url": checkpoint
        }
        
        # --- RSS FAST PATH ---
        try:
            feed = feedparser.parse(self.RSS_URL)
            if feed.entries:
                rss_articles = []
                for entry in feed.entries:
                    link = entry.get("link", "")
                    if checkpoint and (link == checkpoint or link.split("?")[0] == checkpoint.split("?")[0]):
                        self.scrape_metadata["checkpoint_found"] = True
                        self.scrape_metadata["termination_reason"] = "SUCCESS_CHECKPOINT"
                        self.scrape_metadata["exhaustion_evidence"] = "valid"
                        print(f"    [PR Newswire] Fast Path: Checkpoint reached via RSS.")
                        return rss_articles
                    
                    title = entry.get("title", "No title")
                    rss_articles.append({
                        "id": link,
                        "title": title,
                        "url": link,
                        "published": entry.get("published", "")
                    })
                
                if not checkpoint:
                    self.scrape_metadata["checkpoint_found"] = True
                    self.scrape_metadata["termination_reason"] = "SUCCESS_EXHAUSTED"
                    self.scrape_metadata["exhaustion_evidence"] = "valid"
                    print(f"    [PR Newswire] Fast Path: No checkpoint provided, returning {len(rss_articles)} RSS articles.")
                    return rss_articles
                else:
                    self.scrape_metadata["recovery_attempted"] = True
                    self.scrape_metadata["recovery_status"] = "BACKFILL_REQUIRED"
                    self.scrape_metadata["mode"] = "HTML"
                    print(f"    [PR Newswire] Recovery Path: Checkpoint not in RSS, falling back to HTML backfill.")
        except Exception as e:
            self.scrape_metadata["recovery_attempted"] = True
            self.scrape_metadata["recovery_status"] = "BACKFILL_REQUIRED"
            self.scrape_metadata["mode"] = "HTML"
            print(f"    [PR Newswire] RSS Fast Path failed: {e}. Falling back to HTML.")

        # --- HTML RECOVERY PATH (BACKFILL) ---
        articles = []
        for page in range(1, self.scrape_metadata["page_limit"] + 1):
            self.scrape_metadata["pages_visited"] = page
            self.scrape_metadata["pages_scanned"] = page
            url = f"{base_url}?page={page}&pagesize=100"
            headers = {"User-Agent": USER_AGENT}
            
            try:
                response = requests.get(url, headers=headers, impersonate="chrome120", timeout=15)
                if response.status_code != 200:
                    self.scrape_metadata["reason"] = f"HTTP {response.status_code} on page {page}"
                    break
                    
                soup = BeautifulSoup(response.text, "html.parser")
                items = soup.select("a.newsreleaseconsolidatelink")
                
                if not items:
                    self.scrape_metadata["reason"] = f"No items found on page {page}"
                    self.scrape_metadata["termination_reason"] = "SUCCESS_EXHAUSTED"
                    self.scrape_metadata["exhaustion_evidence"] = "valid"
                    self.scrape_metadata["pagination"] = {"has_next_page": False}
                    break
                    
                for item in items:
                    href = item.get("href")
                    if not href: continue
                    full_url = href if href.startswith("http") else f"https://www.prnewswire.com{href}"
                    
                    if checkpoint and (full_url == checkpoint or href == checkpoint):
                        self.scrape_metadata["checkpoint_found"] = True
                        self.scrape_metadata["recovery_status"] = "RECOVERED"
                        self.scrape_metadata["articles_recovered"] = len(articles)
                        self.scrape_metadata["articles_scanned"] = len(articles)
                        self.scrape_metadata["oldest_article_seen"] = full_url
                        self.scrape_metadata["termination_reason"] = "SUCCESS_CHECKPOINT"
                        self.scrape_metadata["exhaustion_evidence"] = "valid"
                        return articles
                        
                    title_elem = item.select_one("h3")
                    title = title_elem.text.split("ET", 1)[-1].strip() if title_elem else "No title"
                    
                    self.scrape_metadata["oldest_article_seen"] = full_url
                    
                    articles.append({
                        "id": full_url,
                        "title": title,
                        "url": full_url,
                        "published": ""
                    })
                    
                time.sleep(1)
                
            except Exception as e:
                print(f"[ERROR] PR Newswire Scraper failed on page {page}: {e}")
                self.scrape_metadata["reason"] = str(e)
                self.scrape_metadata["recovery_status"] = "FAILED"
                break
                
        if self.scrape_metadata["pages_visited"] == self.scrape_metadata["page_limit"] and not self.scrape_metadata.get("checkpoint_found") and checkpoint:
            try:
                # Check if the missing checkpoint is actually a deleted article (404)
                chk_resp = requests.get(checkpoint, impersonate="chrome120", timeout=5)
                if chk_resp.status_code == 404:
                    print(f"    [PR Newswire] Checkpoint {checkpoint} is a 404. Treating gap as closed.")
                    self.scrape_metadata["recovery_status"] = "RECOVERED"
                    self.scrape_metadata["termination_reason"] = "SUCCESS_EXHAUSTED"
                    self.scrape_metadata["exhaustion_evidence"] = "valid"
                else:
                    self.scrape_metadata["recovery_status"] = "GAP_DETECTED"
                    self.scrape_metadata["termination_reason"] = "ARBITRARY_LIMIT_REACHED"
            except Exception:
                self.scrape_metadata["recovery_status"] = "GAP_DETECTED"
                self.scrape_metadata["termination_reason"] = "ARBITRARY_LIMIT_REACHED"
            
        self.scrape_metadata["articles_recovered"] = len(articles)
        self.scrape_metadata["articles_scanned"] = len(articles)
        print(f"    [PR Newswire] Total unique articles fetched: {len(articles)}")
        return articles

    def get_article_body(self, url):
        """
        Extract the full PR body. PR Newswire bodies can be heavy.
        For zero-latency pipeline, we can just return the title placeholder
        if we only need the headline.
        """
        try:
            response = requests.get(url, impersonate="chrome120", timeout=10)
            if response.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, "html.parser")
                body = soup.find("section", class_="release-body container")
                if body:
                    text = body.get_text(separator="\n", strip=True)
                    if text:
                        return text
        except:
            pass
        return "[PR Newswire] Classify event based on Title."
