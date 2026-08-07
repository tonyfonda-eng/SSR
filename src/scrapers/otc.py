import hashlib
from datetime import datetime
from curl_cffi import requests

from src.scrapers.base import SourceScraper

class OTCScraper(SourceScraper):
    """
    OTC Markets Disclosure & News API Scraper.
    Targets the backend OTCIQ JSON feed via curl_cffi to bypass WAFs.
    Extracts zero-latency data directly from the JSON array.
    """
    
    # Primary API endpoint
    API_URL = "https://backend.otcmarkets.com/otcapi/news"
    
    def get_latest_articles(self, **kwargs):
        articles = []
        seen = set()
        
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Origin': 'https://www.otcmarkets.com',
            'Referer': 'https://www.otcmarkets.com/',
        }
        
        try:
            # Query the first page with a solid chunk of articles
            url = f"{self.API_URL}?page=1&pageSize=50"
            
            # Use curl_cffi to bypass Cloudflare/WAF on the backend API
            response = requests.get(url, headers=headers, impersonate="chrome120", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # The API could return a list directly or wrap it in a 'records' or 'data' field
                news_list = data if isinstance(data, list) else data.get('records', [])
                if not news_list and isinstance(data, dict):
                    news_list = data.get('data', [])
                
                for item in news_list:
                    # Every article in OTCIQ has a unique numeric id
                    article_id = str(item.get('id', ''))
                    
                    if not article_id:
                        continue
                        
                    headline = item.get('title', '')
                    # Extract the symbol/ticker
                    symbol = item.get('symbol', 'UNKNOWN')
                    
                    # Deduplication using strict hashing of the unique ID
                    dedupe_hash = hashlib.md5(article_id.encode()).hexdigest()
                    
                    # Construct a full URL so the frontend dashboard has something to click
                    full_url = f"https://www.otcmarkets.com/stock/{symbol}/news/story?id={article_id}"
                    
                    # OTC provides publishedDate in ISO format usually
                    pub_date = item.get('publishedDate', datetime.utcnow().isoformat())
                    
                    if dedupe_hash not in seen:
                        seen.add(dedupe_hash)
                        articles.append({
                            "id": dedupe_hash,
                            "title": f"[{symbol}] {headline}" if symbol != 'UNKNOWN' else headline,
                            "url": full_url,
                            "published": pub_date
                        })
            else:
                print(f"[WARNING] OTC Scraper returned HTTP {response.status_code}")
                
        except Exception as e:
            print(f"[ERROR] OTC Scraper failed: {e}")
            
        print(f"    [OTC Markets] Total unique articles fetched: {len(articles)}")
        return articles

    def get_article_body(self, url):
        """
        Returns empty string. OTC Markets heavily protects full PR body text 
        via their backend API (which is a paid commercial product).
        The AI pipeline will rely solely on the headline for zero-latency event evaluation.
        """
        return ""
