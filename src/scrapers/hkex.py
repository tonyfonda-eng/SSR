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


class HKEXScraper:
    """Dedicated scraper for HKEX corporate disclosures and announcements."""
    
    @staticmethod
    def get_latest_articles(rss_url=None):
        print("[HKEX SCRAPER] Polling Hong Kong Stock Exchange disclosures...")
        url = "https://www1.hkexnews.hk/encs/search/titles?lang=en"
        articles = []
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("result", []):
                    title = item.get("TITLE", "HKEX Disclosure")
                    doc_id = str(item.get("DOC_ID", ""))
                    doc_url = f"https://www1.hkexnews.hk{item.get('FILE_LINK', '')}"
                    articles.append({
                        "id": doc_id,
                        "title": title,
                        "url": doc_url,
                        "published": item.get("DATE", ""),
                        "body": f"HKEX Disclosure for stock code {item.get('STOCK_CODE', '')}: {title}",
                        "document_type": "HKEX Disclosure"
                    })
        except Exception as e:
            print(f"[ERROR] HKEX scraper failed: {e}")
        return articles