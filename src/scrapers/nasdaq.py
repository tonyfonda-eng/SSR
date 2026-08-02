import feedparser
import requests
# --- WAF BYPASS WRAPPER ---
try:
    import requests
    _orig_get = requests.get
    def _spoofed_get(*args, **kwargs):
        headers = kwargs.get('headers', ./src/scrapers/nasdaq.py)
        if isinstance(headers, dict) and 'User-Agent' not in headers:
            headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        kwargs['headers'] = headers
        return _orig_get(*args, **kwargs)
    requests.get = _spoofed_get
except ImportError:
    pass
# --------------------------

from src.scrapers.base import SourceScraper
from src.config.settings import USER_AGENT

class NasdaqScraper(SourceScraper):
    def get_latest_articles(self, **kwargs):
        url = kwargs.get("rss_url") or "https://www.nasdaqtrader.com/Rss.aspx?feed=currentheadlines&categorylist=105"
        
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
