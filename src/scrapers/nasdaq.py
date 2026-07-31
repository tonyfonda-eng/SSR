import feedparser
import requests
from src.scrapers.base import SourceScraper
from src.config.settings import USER_AGENT

class NasdaqScraper(SourceScraper):
    def get_latest_articles(self):
        url = "https://www.nasdaqtrader.com/Rss.aspx?feed=currentheadlines&categorylist=105"
        
        articles = []
        try:
            # Wrap in requests.get with timeout for safety against infinite hangs
            headers = {"User-Agent": USER_AGENT}
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            feed = feedparser.parse(response.content)
            
            for entry in feed.entries:
                # Use the link as the unique ID
                article_id = entry.id if hasattr(entry, 'id') else entry.link
                
                articles.append({
                    "id": article_id,
                    "title": entry.title,
                    "url": entry.link,
                    "published": getattr(entry, 'published', '')
                })
        except Exception as e:
            print(f"[ERROR] Failed to fetch Nasdaq RSS: {e}")
            
        return articles

    def get_article_body(self, url):
        # We don't want to parse HTML right now since this is mostly for alerts (halts, splits).
        # We'll just return a placeholder. The AI will classify based on the Title via the rules engine.
        return "[Nasdaq Trader] Please classify this event based purely on the article Title."
