import requests
from bs4 import BeautifulSoup
import feedparser

from src.scrapers.base import SourceScraper

class EdgarScraper(SourceScraper):
    # Fetch latest 8-K filings
    RSS_URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&company=&dateb=&owner=include&start=0&count=40&output=atom"
    
    # Edgar requires a declared user agent
    USER_AGENT = "SpecialSituationsRadar ssr-admin@special-situations-radar.com"

    def get_latest_articles(self):
        import time
        headers = {"User-Agent": self.USER_AGENT}
        articles = []
        
        # Paginate 5 times, 100 items each = 500 items
        for page in range(5):
            start = page * 100
            url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&company=&dateb=&owner=include&start={start}&count=100&output=atom"
            
            try:
                response = requests.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                feed = feedparser.parse(response.content)
                
                if not feed.entries:
                    break
                    
                for entry in feed.entries:
                    article_id = entry.id
                    articles.append({
                        "id": article_id,
                        "title": entry.title,
                        "url": entry.link,
                        "published": getattr(entry, "published", getattr(entry, "updated", ""))
                    })
                time.sleep(1)
            except Exception as e:
                print(f"[ERROR] Edgar fetch failed on page {page+1}: {e}")
                break
                
        return articles

    def get_article_body(self, url):
        headers = {"User-Agent": self.USER_AGENT}
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        
        # We need to extract the actual text of the filing, which can be tricky in Edgar.
        # Often the main body is in <document> tags or just the body text.
        text = soup.get_text("\n", strip=True)
        if len(text) > 500:
            return text
        return None
