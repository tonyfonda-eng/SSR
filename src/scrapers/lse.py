import requests
# --- WAF BYPASS WRAPPER ---
try:
    import requests
    _orig_get = requests.get
    def _spoofed_get(*args, **kwargs):
        headers = kwargs.get('headers', {})
        if isinstance(headers, dict) and 'User-Agent' not in headers:
            headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        kwargs['headers'] = headers
        return _orig_get(*args, **kwargs)
    requests.get = _spoofed_get
except ImportError:
    pass
# --------------------------

from bs4 import BeautifulSoup
from src.scrapers.base import SourceScraper
from src.config.settings import USER_AGENT

class LSEScraper(SourceScraper):
    """
    London Stock Exchange Scraper.
    Bypasses LSE's Angular CSR anti-bot mechanisms by scraping Investegate (a reliable RNS aggregator).
    """
    
    BASE_URL = "https://www.investegate.co.uk"
    
    def get_latest_articles(self, **kwargs):
        headers = {"User-Agent": USER_AGENT}
        articles = []
        seen = set()
        
        try:
            response = requests.get(self.BASE_URL, headers=headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Find all links to announcements on the homepage
            links = soup.find_all('a', href=True)
            for link in links:
                href = link['href']
                if '/announcement/' in href and '/announcement-archive' not in href:
                    url = href if href.startswith('http') else f"{self.BASE_URL}{href}"
                    article_id = href.split('/')[-1]
                    
                    if article_id not in seen:
                        seen.add(article_id)
                        
                        # Try to find a good title
                        title = link.get_text(strip=True)
                        if not title and link.parent:
                            title = link.parent.get_text(strip=True)
                        if not title:
                            title = f"RNS Announcement {article_id}"
                            
                        articles.append({
                            "id": article_id,
                            "title": title,
                            "url": url,
                            "published": "" # Real-time feed
                        })
                        
        except Exception as e:
            print(f"[ERROR] LSE (Investegate) Scraper failed: {e}")
            
        print(f"    [LSE] Total unique articles fetched: {len(articles)}")
        return articles

    def get_article_body(self, url):
        headers = {"User-Agent": USER_AGENT}
        try:
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code != 200:
                return None
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # The body is usually within a specific container
            main_container = soup.find('div', id='announcementContent') or soup.find('div', class_='container')
            if main_container:
                text = main_container.get_text(separator="\n", strip=True)
                if len(text) > 200:
                    return text
            
            # Fallback to the whole page text
            return soup.get_text(separator="\n", strip=True)
            
        except Exception as e:
            print(f"[WARNING] Failed to fetch LSE article body: {e}")
            
        return None
