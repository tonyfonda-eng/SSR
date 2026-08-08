import requests
from src.scrapers.client import get_session

from bs4 import BeautifulSoup
import feedparser

from src.scrapers.base import SourceScraper
from src.config.settings import USER_AGENT

class GlobeNewswireScraper(SourceScraper):
    RSS_URL = "https://www.globenewswire.com/RssFeed/orgclass/1/feedTitle/GlobeNewswire%20-%20News%20Releases"

    def get_latest_articles(self, **kwargs):
        import time
        from curl_cffi import requests
        import feedparser
        
        checkpoint = kwargs.get("checkpoint")
        
        self.scrape_metadata = {
            "source": "GlobeNewswire",
            "mode": "RSS",
            "checkpoint_found": False,
            "emergency_stop": False,
            "reason": "",
            "last_checkpoint_url": checkpoint
        }
        
        articles = []
        try:
            r = requests.get(self.RSS_URL, headers={"User-Agent": USER_AGENT}, impersonate="chrome120", timeout=15)
            feed = feedparser.parse(r.text)
            
            for entry in feed.entries:
                link = entry.get("link", "")
                if checkpoint and (link == checkpoint or link.split("?")[0] == checkpoint.split("?")[0]):
                    self.scrape_metadata["checkpoint_found"] = True
                    break
                    
                articles.append({
                    "id": link,
                    "title": entry.get("title", "No title"),
                    "url": link,
                    "published": entry.get("published", "")
                })
        except Exception as e:
            self.scrape_metadata["reason"] = f"RSS Feed fetch failed: {e}"
            print(f"[ERROR] GlobeNewswire Scraper failed: {e}")
            
        print(f"    [GlobeNewswire] Total unique articles fetched: {len(articles)}")
        return articles

    def get_article_body(self, url):
        from curl_cffi import requests
        from bs4 import BeautifulSoup
        
        try:
            response = requests.get(url, headers={"User-Agent": USER_AGENT}, impersonate="chrome120", timeout=15)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                
                # GlobeNewswire specific selectors
                article = soup.select_one("div.article-body") or soup.select_one("main")
                
                if article:
                    text = article.get_text("\n", strip=True)
                    if len(text) > 500:
                        return text
        except Exception as e:
            pass
            
        return "[GlobeNewswire] Classify event based on Title."
