import time
from curl_cffi import requests
from bs4 import BeautifulSoup

from src.scrapers.base import SourceScraper
from src.config.settings import USER_AGENT

class HKEXScraper(SourceScraper):
    """
    Dedicated scraper for Hong Kong Exchange (HKEX).
    Includes mandatory delay to respect their aggressive firewall.
    """
    
    # Official daily index log payload link
    TARGET_URL = "https://www1.hkexnews.hk/search/titlesearch.xhtml?lang=en"
    
    def get_latest_articles(self, **kwargs):
        url = kwargs.get("url") or self.TARGET_URL
        articles = []
        
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
        }
        
        try:
            # Mandatory 3-second delay to prevent triggering an instant IP ban
            print("    [HKEX] Sleeping 3 seconds to respect rate limits...")
            time.sleep(3)
            
            response = requests.get(url, headers=headers, impersonate="chrome120", timeout=15)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                
                # HKEX typically stores these in a table with class 'table'
                table = soup.find("table", class_="table")
                if table:
                    for row in table.find_all("tr")[1:]:
                        cols = row.find_all("td")
                        if len(cols) >= 4:
                            date = cols[0].get_text(strip=True)
                            code = cols[1].get_text(strip=True)
                            
                            link_tag = cols[3].find("a")
                            if link_tag:
                                title = link_tag.get_text(strip=True)
                                relative_url = link_tag.get("href", "")
                                full_url = f"https://www1.hkexnews.hk{relative_url}" if relative_url.startswith("/") else relative_url
                                
                                articles.append({
                                    "id": full_url,
                                    "title": f"[{code}] {title}",
                                    "url": full_url,
                                    "published": date
                                })
            else:
                print(f"[WARNING] HKEX Scraper returned HTTP {response.status_code}")
                
        except Exception as e:
            print(f"[ERROR] HKEX Scraper failed: {e}")
            
        print(f"    [HKEX] Total unique articles fetched: {len(articles)}")
        return articles

    def get_article_body(self, url):
        return "[HKEX PDF] Classify event based on Title."