import requests

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