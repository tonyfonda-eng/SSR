
def _safe_json(resp):
    try: return resp.json()
    except Exception:
        print("    [ASX WAF] HTML Challenge Blocked JSON payload. Skipping.")
        return {}
import requests
from src.scrapers.client import get_session


class ASXScraper:
    """Dedicated scraper for ASX corporate announcements."""
    
    @staticmethod
    def get_latest_articles(**kwargs):
        print("[ASX SCRAPER] Polling Australian Stock Exchange announcements...")
        url = kwargs.get('url') or kwargs.get('rss_url') or "https://www.asx.com.au/asx/v2/statistics/announcements.do?by=latest&timeframe=d&fmt=json"
        articles = []
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = get_session().get(url, headers=headers, timeout=15)
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