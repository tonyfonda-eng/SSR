import requests
from bs4 import BeautifulSoup
import feedparser

from src.scrapers.base import SourceScraper
from src.config.settings import USER_AGENT

class BusinessWireScraper(SourceScraper):
    RSS_URL = "https://feed.businesswire.com/rss/home/?rss=G1QFDERJXkJeGVtQWA%3D%3D"

    def get_latest_articles(self):
        feed = feedparser.parse(self.RSS_URL)
        articles = []
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
