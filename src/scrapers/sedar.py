import requests
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