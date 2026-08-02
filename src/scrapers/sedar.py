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

class SedarScraper:
    """Dedicated scraper for SEDAR+ Canadian regulatory filings and prospectuses."""
    
    @staticmethod
    def get_latest_articles(rss_url=None):
        print("[SEDAR+ SCRAPER] Polling Canadian regulatory filings...")
        target_url = rss_url or "https://www.sedarplus.ca/csa-party/rss/latest_filings.rss"
        articles = []
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(target_url, headers=headers, timeout=15)
            if resp.status_code == 200:
                feed = feedparser.parse(resp.content)
                for entry in feed.entries:
                    articles.append({
                        "id": entry.link.rstrip("/").split("/")[-1],
                        "title": entry.title,
                        "url": entry.link,
                        "published": getattr(entry, "published", ""),
                        "body": getattr(entry, "summary", getattr(entry, "description", "")),
                        "document_type": "SEDAR+ Regulatory Filing"
                    })
        except Exception as e:
            print(f"[ERROR] SEDAR+ scraper failed: {e}")
        return articles