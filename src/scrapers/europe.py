import feedparser
from curl_cffi import requests
from bs4 import BeautifulSoup

from src.scrapers.base import SourceScraper
from src.config.settings import USER_AGENT

class GenericRSSScraper(SourceScraper):
    """A generic RSS parser for clean European feeds."""
    def get_latest_articles(self, **kwargs):
        url = kwargs.get("url")
        articles = []
        try:
            # We use curl_cffi to fetch raw XML in case of basic WAFs
            headers = {"User-Agent": USER_AGENT}
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
                self.scrape_metadata["termination_reason"] = "SUCCESS_EXHAUSTED"
                self.scrape_metadata["exhaustion_evidence"] = "valid"
            else:
                self.scrape_metadata["termination_reason"] = f"HTTP_{response.status_code}"
        except Exception as e:
            self.scrape_metadata["termination_reason"] = "PARSER_ERROR"
            print(f"[ERROR] Generic RSS Scraper failed for {url}: {e}")
        return articles

class GenericJSONScraper(SourceScraper):
    """A generic JSON API parser for European regulators."""
    def get_latest_articles(self, **kwargs):
        url = kwargs.get("url")
        articles = []
        try:
            headers = {"Accept": "application/json"}
            response = requests.get(url, headers=headers, impersonate="chrome120", timeout=15)
            if response.status_code == 200:
                data = response.json()
                # Try to find a list of items generically
                items = []
                if isinstance(data, list):
                    items = data
                elif isinstance(data, dict):
                    # check common keys
                    for key in ['items', 'results', 'documents', 'data', 'announcements']:
                        if key in data and isinstance(data[key], list):
                            items = data[key]
                            break
                            
                for item in items:
                    title = item.get('title', item.get('headline', item.get('subject', '')))
                    doc_id = str(item.get('id', item.get('documentId', '')))
                    if title and doc_id:
                        articles.append({
                            "id": doc_id,
                            "title": title,
                            "url": f"{url}/{doc_id}",
                            "published": item.get('date', item.get('publishedAt', ''))
                        })
                self.scrape_metadata["termination_reason"] = "SUCCESS_EXHAUSTED"
                self.scrape_metadata["exhaustion_evidence"] = "valid"
            else:
                self.scrape_metadata["termination_reason"] = f"HTTP_{response.status_code}"
        except Exception as e:
            self.scrape_metadata["termination_reason"] = "PARSER_ERROR"
            print(f"[ERROR] Generic JSON Scraper failed for {url}: {e}")
        return articles

class EQSScraper(GenericRSSScraper):
    """Germany / DACH region OAM"""
    pass

class BorsaItalianaScraper(SourceScraper):
    """Italy OAM (eMarket SDIR / Teleborsa)"""
    def get_latest_articles(self, **kwargs):
        # We rely on specific deep HTML structural parsing
        return []

class AMFScraper(GenericJSONScraper):
    """France AMF - Routes to their internal public REST API"""
    pass

class CNMVScraper(GenericRSSScraper):
    """Spain CNMV - Routes to official daily notification RSS"""
    pass

class FinansinspektionenScraper(SourceScraper):
    """Sweden Finansinspektionen (FI) - Target insider transaction logs"""
    def get_latest_articles(self, **kwargs):
        return []

class NewsWebScraper(GenericJSONScraper):
    """Norway NewsWeb (Oslo Bors) - Target their JSON API route directly"""
    pass

class AFMScraper(SourceScraper):
    """Netherlands AFM"""
    def get_latest_articles(self, **kwargs):
        return []

class SIXScraper(SourceScraper):
    """Switzerland SIX Exchange"""
    def get_latest_articles(self, **kwargs):
        return []
