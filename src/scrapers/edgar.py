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
import feedparser

from src.scrapers.base import SourceScraper

class EdgarScraper(SourceScraper):
    # Base class for EDGAR polling. Default is 8-K.
    FILING_TYPE = "8-K"
    
    # Edgar requires a declared user agent
    USER_AGENT = "SpecialSituationsRadar ssr-admin@special-situations-radar.com"

    def get_latest_articles(self, **kwargs):
        import time
        headers = {"User-Agent": self.USER_AGENT}
        articles = []
        
        # Paginate 5 times, 100 items each = 500 items
        for page in range(5):
            start = page * 100
            url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type={self.FILING_TYPE}&company=&dateb=&owner=include&start={start}&count=100&output=atom"
            
            try:
                response = requests.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                feed = feedparser.parse(response.content)
                
                if not feed.entries:
                    break
                    
                for entry in feed.entries:
                    article_id = entry.id
                    articles.append({
                        "id": article_id,
                        "title": entry.title,
                        "url": entry.link,
                        "published": getattr(entry, "published", getattr(entry, "updated", ""))
                    })
                time.sleep(1)
            except Exception as e:
                print(f"[ERROR] Edgar fetch failed on page {page+1} for {self.FILING_TYPE}: {e}")
                break
                
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

class Edgar13DScraper(EdgarScraper):
    FILING_TYPE = "13D"

class EdgarForm10Scraper(EdgarScraper):
    FILING_TYPE = "10-12B"

class EdgarTenderOfferScraper(EdgarScraper):
    FILING_TYPE = "SC TO"

class Edgar14D9Scraper(EdgarScraper):
    FILING_TYPE = "SC 14D9"

class EdgarMergerProxyScraper(EdgarScraper):
    FILING_TYPE = "PREM14A"

class EdgarDefinitiveProxyScraper(EdgarScraper):
    FILING_TYPE = "DEFM14A"

class EdgarS4Scraper(EdgarScraper):
    FILING_TYPE = "S-4"
