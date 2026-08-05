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

class TSXScraper:
    """Dedicated scraper for TSX and Canadian newswire feeds."""
    
    @staticmethod
    def get_latest_articles(**kwargs):
        print("[TSX SCRAPER] Polling Canadian exchange feeds...")
        target_url = kwargs.get('url') or kwargs.get('rss_url') or "https://www.tsx.com/news/rss"
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
                        "document_type": "Canadian Regulatory Filing"
                    })
        except Exception as e:
            print(f"[ERROR] TSX scraper failed: {e}")
        return articles