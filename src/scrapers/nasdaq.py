import hashlib
from curl_cffi import requests
from bs4 import BeautifulSoup

from src.scrapers.base import SourceScraper
from src.config.settings import USER_AGENT

class NasdaqScraper(SourceScraper):
    """
    Nasdaq Trader Alerts Scraper.
    Targets the specific ETP/Corporate Action listings endpoint (cat_id=105)
    Bypasses standard DOM scraping via deterministic table extraction.
    """
    
    def get_latest_articles(self, **kwargs):
        # Targeted micro-layout feed link
        target_url = "https://www.nasdaqtrader.com/Micro.aspx?id=MicroArchiveHeadlines&cat_id=105"
        
        # Standard security headers to clear basic Akamai/Edge security fences
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
        
        articles = []
        seen = set()
        
        try:
            response = requests.get(target_url, headers=headers, impersonate="chrome120", timeout=10)
            
            if response.status_code != 200:
                print(f"[WARNING] Nasdaq Scraper returned HTTP {response.status_code}")
                return []
                
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Nasdaq formats these indices inside a standard visual data table
            table = soup.find("table")
            if not table:
                # Can occasionally be empty during off-market hours or missing alerts
                print("[WARNING] Nasdaq Scraper: No table found on the page.")
                return []
                
            # Skip the header row and iterate over the table data rows
            for row in table.find_all("tr")[1:]:
                cols = row.find_all("td")
                if len(cols) < 3:
                    continue
                    
                date = cols[0].get_text(strip=True)
                
                # Look for the internal relative anchor reference
                link_tag = cols[2].find("a")
                if not link_tag:
                    continue
                    
                headline = link_tag.get_text(strip=True)
                relative_url = link_tag.get("href")
                
                if relative_url:
                    full_url = f"https://www.nasdaqtrader.com{relative_url}" if relative_url.startswith("/") else relative_url
                else:
                    continue
                
                # OPTIMIZATION: Extract Nasdaq's internal Alert ID string from the text
                # Example format: "Trader Alerts - New ETP Listings #2026-105" -> "2026-105"
                alert_id = headline.split("#")[-1].strip() if "#" in headline else relative_url
                
                # Precision Deduplication: Hash the Alert ID + Ticker name context
                dedupe_hash = hashlib.md5(alert_id.encode()).hexdigest()
                
                if dedupe_hash not in seen:
                    seen.add(dedupe_hash)
                    articles.append({
                        "id": dedupe_hash,
                        "title": headline,
                        "url": full_url,
                        "published": date
                    })
                    
        except Exception as e:
            print(f"[ERROR] Nasdaq Scraper failed: {e}")
            
        print(f"    [Nasdaq] Total unique articles fetched: {len(articles)}")
        return articles

    def get_article_body(self, url):
        """
        Extracts the exact body from the Trader Alert page if needed, but the AI 
        usually evaluates based on the title (which contains the ticker and action).
        """
        try:
            response = requests.get(url, impersonate="chrome120", timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                # Nasdaq typically puts content in a div with id 'content'
                content_div = soup.find("div", id="content") or soup.find("div", id="archHeadlinesDiv")
                if content_div:
                    for element in content_div(["script", "style", "nav"]):
                        element.decompose()
                    return content_div.get_text(separator="\n", strip=True)
        except Exception as e:
            print(f"[WARNING] Failed to fetch Nasdaq article body: {e}")
            
        return "[Nasdaq Trader] Please classify this event based purely on the article Title."
