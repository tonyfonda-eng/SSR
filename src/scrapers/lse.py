import requests
from src.scrapers.client import get_session

from bs4 import BeautifulSoup
from src.scrapers.base import SourceScraper
from src.config.settings import USER_AGENT

class LSEScraper(SourceScraper):
    """
    London Stock Exchange Scraper.
    Hardened against TCP Tarpits and WAF infinite-streams.
    """
    
    BASE_URL = "https://www.investegate.co.uk"
    
    def get_latest_articles(self, **kwargs):
        headers = {"User-Agent": USER_AGENT}
        articles = []
        seen = set()
        
        try:
            # Tuple timeout: (3s connect limit, 5s read limit per byte)
            response = get_session().get(self.BASE_URL, headers=headers, timeout=(3.0, 5.0), stream=True)
            response.raise_for_status()
            
            # WAF Safeguard: Ensure they didn't serve a massive tarball to crash memory
            content_type = response.headers.get('Content-Type', '')
            if 'text/html' not in content_type:
                raise ValueError(f"WAF Blocked: Received invalid Content-Type: {content_type}")
                
            # Read first 1MB only to prevent infinite stream tarpits
            html_content = response.raw.read(1000000) 
            soup = BeautifulSoup(html_content, "html.parser")
            
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
                        
        except requests.exceptions.Timeout:
            print("[ERROR] LSE Scraper timed out (Caught in WAF Tarpit). Skipping.")
        except Exception as e:
            print(f"[ERROR] LSE (Investegate) Scraper failed: {e}")
            
        print(f"    [LSE] Total unique articles fetched: {len(articles)}")
        return articles

    def get_article_body(self, url):
        headers = {"User-Agent": USER_AGENT}
        try:
            response = get_session().get(url, headers=headers, timeout=(3.0, 5.0), stream=True)
            if response.status_code != 200:
                return None
                
            # WAF Safeguard: Only read up to 1MB
            html_content = response.raw.read(1000000)
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # The body is usually within a specific container
            main_container = soup.find('div', id='announcementContent') or soup.find('div', class_='container')
            if main_container:
                text = main_container.get_text(separator="\n", strip=True)
                if len(text) > 200:
                    return text
            
            # Fallback to the whole page text
            return soup.get_text(separator="\n", strip=True)
            
        except requests.exceptions.Timeout:
            print(f"[WARNING] Failed to fetch LSE article body (Timeout): {url}")
        except Exception as e:
            print(f"[WARNING] Failed to fetch LSE article body: {e}")
            
        return None