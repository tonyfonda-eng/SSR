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

import feedparser
import time

from src.scrapers.base import SourceScraper


class EdgarItemScraper(SourceScraper):
    """
    Fetches SEC EDGAR 8-K filings filtered by material item codes.
    Uses the EDGAR full-text search API (efts.sec.gov) for structured results.
    
    Target item codes:
        1.01 - Entry into Material Definitive Agreement (mergers, acquisitions)
        2.01 - Completion of Acquisition or Disposition (deal closings)
        5.01 - Changes in Control (going-private, squeeze-outs)
        8.01 - Other Events (special dividends, liquidations, etc.)
    """
    
    USER_AGENT = "SpecialSituationsRadar ssr-admin@special-situations-radar.com"
    
    # EDGAR EFTS API for full-text search
    EFTS_BASE = "https://efts.sec.gov/LATEST/search-index"
    
    # EDGAR Atom feed (more reliable, structured)
    ATOM_BASE = "https://www.sec.gov/cgi-bin/browse-edgar"
    
    # Item codes we care about
    TARGET_ITEMS = ["1.01", "2.01", "5.01", "8.01"]

    def get_latest_articles(self, **kwargs):
        headers = {"User-Agent": self.USER_AGENT}
        articles = []
        seen_ids = set()
        
        # Use the EDGAR full-text search API for recent 8-K filings
        # The EFTS API returns JSON with filing metadata
        try:
            url = (
                "https://efts.sec.gov/LATEST/search-index"
                "?q=%228-K%22&dateRange=custom&startdt=&enddt="
                "&forms=8-K&hits=100"
            )
            response = requests.get(url, headers=headers, timeout=30)
            
            # EFTS may not be available; fall back to Atom feed approach
            if response.status_code != 200:
                print("[INFO] EFTS API unavailable. Using EDGAR Atom feed for 8-K items.")
                return self._fetch_via_atom(headers)
                
            data = response.json()
            hits = data.get("hits", {}).get("hits", [])
            
            for hit in hits:
                source = hit.get("_source", {})
                filing_id = hit.get("_id", "")
                
                if filing_id in seen_ids:
                    continue
                seen_ids.add(filing_id)
                
                # Check if any target item codes are present
                items = source.get("items", "")
                has_target_item = any(item in items for item in self.TARGET_ITEMS)
                
                if not has_target_item:
                    continue
                
                file_url = source.get("file_url", "")
                if not file_url:
                    continue
                    
                full_url = f"https://www.sec.gov{file_url}" if not file_url.startswith("http") else file_url
                
                articles.append({
                    "id": filing_id,
                    "title": f"8-K [{items}] - {source.get('company_name', 'Unknown')}",
                    "url": full_url,
                    "published": source.get("file_date", ""),
                    "body": source.get("file_description", "")
                })
                
        except Exception as e:
            print(f"[WARNING] EFTS search failed: {e}. Falling back to Atom feed.")
            return self._fetch_via_atom(headers)
            
        if not articles:
            # Fallback if EFTS returned no results
            return self._fetch_via_atom(headers)
            
        return articles
    
    def _fetch_via_atom(self, headers):
        """
        Fallback: fetch recent 8-K filings via the standard EDGAR Atom feed.
        Less structured than EFTS but more reliable.
        """
        articles = []
        seen_ids = set()
        
        # Fetch 3 pages of 100 items each
        for page in range(3):
            start = page * 100
            url = (
                f"https://www.sec.gov/cgi-bin/browse-edgar"
                f"?action=getcurrent&type=8-K&company=&dateb="
                f"&owner=include&start={start}&count=100&output=atom"
            )
            
            try:
                response = requests.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                feed = feedparser.parse(response.content)
                
                if not feed.entries:
                    break
                    
                for entry in feed.entries:
                    filing_id = entry.id
                    if filing_id in seen_ids:
                        continue
                    seen_ids.add(filing_id)
                    
                    # The Atom feed title often contains item codes
                    title = entry.title
                    has_target_item = any(item in title for item in self.TARGET_ITEMS)
                    
                    if not has_target_item:
                        continue
                    
                    articles.append({
                        "id": filing_id,
                        "title": title,
                        "url": entry.link,
                        "published": getattr(entry, "published", getattr(entry, "updated", ""))
                    })
                time.sleep(1)
            except Exception as e:
                print(f"[ERROR] EDGAR 8-K Items Atom fetch failed on page {page+1}: {e}")
                break
                
        return articles

    def get_article_body(self, url):
        """
        Fetches the full text of an EDGAR filing.
        """
        headers = {"User-Agent": self.USER_AGENT}
        try:
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code != 200:
                return None
                
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, "html.parser")
            text = soup.get_text("\n", strip=True)
            if len(text) > 500:
                return text
        except Exception as e:
            print(f"[ERROR] Failed to fetch EDGAR filing body: {e}")
        return None
