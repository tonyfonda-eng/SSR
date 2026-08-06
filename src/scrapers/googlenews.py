import feedparser
import urllib.parse
import time
import requests
from src.scrapers.client import get_session

from bs4 import BeautifulSoup
from src.scrapers.base import SourceScraper
from src.config.settings import USER_AGENT

class GoogleNewsScraper(SourceScraper):
    def get_latest_articles(self, **kwargs):
        # Allow subclasses to define their own query
        query = getattr(self, 'query', 'merger OR acquisition OR buyout OR "tender offer" OR "special dividend" OR "stock buyback" OR "take-private"')
        encoded_query = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
        
        articles = []
        try:
            # Wrap in requests.get with timeout for safety
            headers = {"User-Agent": USER_AGENT}
            response = get_session().get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            feed = feedparser.parse(response.content)
            
            for entry in feed.entries:
                # Use the Google News article ID as the unique ID
                article_id = entry.id if hasattr(entry, 'id') else entry.link
                
                # Google News puts the source at the end of the title, e.g. "... - Yahoo Finance"
                title = entry.title
                
                article_data = {
                    "id": article_id,
                    "title": title,
                    "url": entry.link,
                    "published": getattr(entry, 'published', '')
                }
                
                doc_type = getattr(self, 'document_type', None)
                if doc_type:
                    article_data['document_type'] = doc_type
                    
                articles.append(article_data)
        except Exception as e:
            print(f"[ERROR] Failed to fetch Google News RSS: {e}")
            
        return articles

    def get_article_body(self, url):
        # We don't want to follow the Google News redirect and try to scrape 100 different websites (WSJ, Bloomberg, etc).
        # We'll just return a placeholder. The AI will classify based on the Title, which is passed in separately in the pipeline anyway!
        # Wait, the pipeline passes the 'body' to classify_event. If body is empty, it relies on 'title' via the 'matches' rules engine context.
        # But to be safe, we can fetch the RSS again or just return a string saying "Classify based on Title."
        return "[Google News Aggregator] Please classify this event based purely on the article Title."
