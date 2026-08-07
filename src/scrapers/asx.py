from curl_cffi import requests
from src.scrapers.base import SourceScraper

class ASXScraper(SourceScraper):
    """
    Dedicated scraper for ASX corporate announcements.
    Uses curl_cffi to bypass the aggressive HTML Challenge WAF.
    """
    
    # Modern dynamic JSON API endpoint
    API_URL = "https://asx.api.markitdigital.com/asx-research/v1/companies/announcements"
    
    def get_latest_articles(self, **kwargs):
        url = kwargs.get("url") or self.API_URL
        articles = []
        
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://www2.asx.com.au",
            "Referer": "https://www2.asx.com.au/"
        }
        
        try:
            # impersonate chrome120 to pass the WAF
            response = requests.get(url, headers=headers, impersonate="chrome120", timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                
                # The announcements are usually embedded in a 'data' array
                items = data.get("data", {}).get("items", []) if isinstance(data, dict) and "data" in data else []
                if not items and isinstance(data, list):
                    items = data
                    
                for item in items:
                    headline = item.get("headline", "")
                    doc_id = item.get("id", "")
                    symbol = item.get("symbol", "ASX")
                    
                    if not doc_id:
                        continue
                        
                    full_url = f"https://cdn-api.markitdigital.com/apiman-gateway/ASX/asx-research/1.0/file/{doc_id}"
                    
                    articles.append({
                        "id": doc_id,
                        "title": f"[{symbol}] {headline}",
                        "url": full_url,
                        "published": item.get("date", "")
                    })
            else:
                print(f"[WARNING] ASX Scraper returned HTTP {response.status_code}")
                
        except Exception as e:
            print(f"[ERROR] ASX Scraper failed: {e}")
            
        print(f"    [ASX] Total unique articles fetched: {len(articles)}")
        return articles

    def get_article_body(self, url):
        return "[ASX PDF] Classify event based on Title."