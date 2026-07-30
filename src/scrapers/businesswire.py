import requests
from bs4 import BeautifulSoup
import feedparser

from src.scrapers.base import SourceScraper
from src.config.settings import USER_AGENT

class BusinessWireScraper(SourceScraper):
    RSS_URL = "https://feed.businesswire.com/rss/home/?rss=G1QFDERJXkJeGVtQWA%3D%3D"

    def get_latest_articles(self):
        import time
        headers = {"User-Agent": USER_AGENT}
        articles = []
        
        # Try HTML Pagination first
        try:
            for page in range(1, 4):
                url = f"https://www.businesswire.com/portal/site/home/news/?paging=true&page={page}"
                response = requests.get(url, headers=headers, timeout=15)
                
                # If bot protection blocks us (e.g. 403), fallback immediately
                if response.status_code != 200:
                    break
                    
                soup = BeautifulSoup(response.text, "html.parser")
                article_links = soup.select("a.bwTitleLink")
                
                if not article_links:
                    break
                    
                for a_tag in article_links:
                    href = a_tag.get('href')
                    if not href:
                        continue
                        
                    full_url = href if href.startswith("http") else "https://www.businesswire.com" + href
                    article_id = full_url.rstrip("/").split("/")[-2] if len(full_url.split("/")) > 2 else full_url
                    
                    articles.append({
                        "id": article_id,
                        "title": a_tag.get_text(strip=True),
                        "url": full_url,
                        "published": ""
                    })
                time.sleep(1)
                
            if articles:
                return articles
        except Exception as e:
            print(f"[WARNING] BusinessWire HTML pagination failed: {e}. Falling back to RSS.")
            
        # Fallback to multi-RSS strategy if HTML scraping fails or is blocked
        print("[INFO] BusinessWire using multi-RSS fallback.")
        
        # BusinessWire provides multiple category feeds. We merge them to bypass the 30-item limit.
        rss_feeds = [
            "https://feed.businesswire.com/rss/home/?rss=G1QFDERJXkJeGVtQWA%3D%3D", # Global News
            "https://feed.businesswire.com/rss/home/?rss=G1QFDERJXkJeGVtQXg%3D%3D", # Earnings
            "https://feed.businesswire.com/rss/home/?rss=G1QFDERJXkJeGVtQXA%3D%3D", # Mergers & Acquisitions
            "https://feed.businesswire.com/rss/home/?rss=G1QFDERJXkJeGVtRWg%3D%3D", # Venture Capital
            "https://feed.businesswire.com/rss/home/?rss=G1QFDERJXkJeGVtQWw%3D%3D", # Technology
            "https://feed.businesswire.com/rss/home/?rss=G1QFDERJXkJeGVtQWg%3D%3D", # Healthcare
        ]
        
        seen_ids = set()
        
        for feed_url in rss_feeds:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries:
                    article_id = entry.link.split("/")[-2] if len(entry.link.split("/")) > 2 else entry.link
                    
                    if article_id not in seen_ids:
                        seen_ids.add(article_id)
                        articles.append({
                            "id": article_id,
                            "title": entry.title,
                            "url": entry.link,
                            "published": getattr(entry, "published", "")
                        })
            except Exception as e:
                print(f"[WARNING] Failed to parse BusinessWire feed {feed_url}: {e}")
                
        return articles

    def get_article_body(self, url):
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        
        # Business Wire specific selectors
        article = soup.select_one("div.bw-release-story") or soup.select_one("main")
        
        if article:
            text = article.get_text("\n", strip=True)
            if len(text) > 500:
                return text
        return None
