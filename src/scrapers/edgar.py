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
        # Using requests to pass the specific User-Agent before parsing with feedparser
        headers = {"User-Agent": self.USER_AGENT}
        try:
            response = requests.get(self.RSS_URL, headers=headers, timeout=30)
            response.raise_for_status()
            feed = feedparser.parse(response.content)
        except Exception as e:
            print(f"[ERROR] Edgar fetch failed: {e}")
            return []

        articles = []
        for entry in feed.entries:
            article_id = entry.id
            articles.append({
                "id": article_id,
                "title": entry.title,
                "url": entry.link,
                "published": getattr(entry, "published", getattr(entry, "updated", ""))
            })
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
