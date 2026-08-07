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
        
        base_url = "https://www.prnewswire.com/news-releases/news-releases-list/"
        articles = []
        checkpoint = kwargs.get("checkpoint")
        
        self.scrape_metadata = {
            "pages_visited": 0,
            "page_limit": 20,
            "checkpoint_found": False,
            "emergency_stop": False,
            "reason": "",
            "last_checkpoint_url": checkpoint
        }
        
        for page in range(1, self.scrape_metadata["page_limit"] + 1):
            self.scrape_metadata["pages_visited"] = page
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
                    break
                    
                for item in items:
                    href = item.get("href")
                    if not href: continue
                    full_url = href if href.startswith("http") else f"https://www.prnewswire.com{href}"
                    
                    if checkpoint and (full_url == checkpoint or href == checkpoint):
                        self.scrape_metadata["checkpoint_found"] = True
                        return articles
                        
                    title_elem = item.select_one("h3")
                    title = title_elem.text.split("ET", 1)[-1].strip() if title_elem else "No title"
                    
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
                break
                
        if self.scrape_metadata["pages_visited"] == self.scrape_metadata["page_limit"] and not self.scrape_metadata.get("checkpoint_found") and checkpoint:
            self.scrape_metadata["emergency_stop"] = True
            
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
                    return body.get_text(separator="\n", strip=True)
        except:
            pass
        return "[PR Newswire] Classify event based on Title."
