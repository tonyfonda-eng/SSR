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
        url = kwargs.get("url") or self.RSS_URL
        articles = []
        
        headers = {"User-Agent": USER_AGENT}
        
        try:
            # We use curl_cffi to ensure any basic WAF caching is cleared
            response = requests.get(url, headers=headers, impersonate="chrome120", timeout=15)
            
            if response.status_code == 200:
                feed = feedparser.parse(response.content)
                
                for entry in feed.entries:
                    article_id = entry.id if hasattr(entry, 'id') else entry.link
                    
                    articles.append({
                        "id": article_id,
                        "title": entry.title,
                        "url": entry.link,
                        "published": getattr(entry, 'published', '')
                    })
            else:
                print(f"[WARNING] PR Newswire Scraper returned HTTP {response.status_code}")
                
        except Exception as e:
            print(f"[ERROR] PR Newswire Scraper failed: {e}")
            
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
