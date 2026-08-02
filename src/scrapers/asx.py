
def _safe_json(resp):
    try: return _safe_json(resp)
    except Exception:
        print("    [ASX WAF] HTML Challenge Blocked JSON payload. Skipping.")
        return {}
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


class ASXScraper:
    """Dedicated scraper for ASX corporate announcements."""
    
    @staticmethod
    def get_latest_articles(rss_url=None):
        print("[ASX SCRAPER] Polling Australian Stock Exchange announcements...")
        url = "https://www.asx.com.au/asx/v2/statistics/announcements.do?by=latest&timeframe=d&fmt=json"
        articles = []
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                data = _safe_json(resp)
                for item in data.get("data", []):
                    title = item.get("documentHeadline", "ASX Announcement")
                    ann_id = str(item.get("announcementId", ""))
                    doc_num = item.get("documentKey", "")
                    doc_url = f"https://www.asx.com.au/asxpdf/{doc_num}.pdf"
                    articles.append({
                        "id": ann_id,
                        "title": title,
                        "url": doc_url,
                        "published": item.get("date", ""),
                        "body": f"ASX Corporate Announcement for {item.get('issuerCode', 'ASX')}: {title}",
                        "document_type": "ASX Announcement"
                    })
        except Exception as e:
            print(f"[ERROR] ASX scraper failed: {e}")
        return articles