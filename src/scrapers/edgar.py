import requests
from src.scrapers.client import get_session

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
        checkpoint = kwargs.get("checkpoint")
        
        page = 0
        while True:
            start = page * 100
            url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type={self.FILING_TYPE}&company=&dateb=&owner=include&start={start}&count=100&output=atom"
            
            try:
                response = get_session().get(url, headers=headers, timeout=30)
                response.raise_for_status()
                feed = feedparser.parse(response.content)
                
                if not feed.entries:
                    break
                    
                for entry in feed.entries:
                    article_id = entry.id
                    article_link = entry.link
                    
                    if checkpoint and (article_id == checkpoint or article_link == checkpoint):
                        return articles
                        
                    articles.append({
                        "id": article_id,
                        "title": entry.title,
                        "url": article_link,
                        "published": getattr(entry, "published", getattr(entry, "updated", ""))
                    })
                    
                time.sleep(1)
                page += 1
            except Exception as e:
                print(f"[ERROR] Edgar fetch failed on page {page+1} for {self.FILING_TYPE}: {e}")
                break
                
        return articles

    def get_article_body(self, url):
        headers = {"User-Agent": self.USER_AGENT}
        try:
            response = get_session().get(url, headers=headers, timeout=30)
            if response.status_code != 200:
                return None
            
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, "html.parser")
            
            # If we landed on an index page, fetch the actual document
            if "index.htm" in url:
                table = soup.find("table", class_="tableFile", summary="Document Format Files")
                if table:
                    rows = table.find_all("tr")
                    for row in rows[1:]:
                        cols = row.find_all("td")
                        if len(cols) >= 3:
                            doc_link = cols[2].find("a")
                            if doc_link:
                                href = doc_link.get("href")
                                # Ignore iXBRL viewer wrapper and get raw file
                                if href.startswith("/ix?doc="):
                                    href = href.replace("/ix?doc=", "")
                                    
                                if href.lower().endswith(".htm") or href.lower().endswith(".txt"):
                                    real_url = f"https://www.sec.gov{href}" if href.startswith("/") else href
                                    # Fetch the real document
                                    doc_resp = get_session().get(real_url, headers=headers, timeout=30)
                                    if doc_resp.status_code == 200:
                                        doc_soup = BeautifulSoup(doc_resp.text, "html.parser")
                                        text = doc_soup.get_text("
", strip=True)
                                        if len(text) > 500:
                                            return text
                                    break # If we failed to get the primary doc, don't fallback to index text
            
            # Fallback if not an index page or extraction failed
            text = soup.get_text("
", strip=True)
            if len(text) > 500:
                return text
        except Exception as e:
            print(f"[ERROR] Failed to fetch EDGAR filing body: {e}")
            
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
