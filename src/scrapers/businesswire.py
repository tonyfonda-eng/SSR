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
            
        # Fallback to RSS if HTML scraping fails or is blocked
        print("[INFO] BusinessWire using RSS fallback.")
        feed = feedparser.parse(self.RSS_URL)
        for entry in feed.entries:
            article_id = entry.link.split("/")[-2] if len(entry.link.split("/")) > 2 else entry.link
            articles.append({
                "id": article_id,
                "title": entry.title,
                "url": entry.link,
                "published": getattr(entry, "published", "")
            })
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
