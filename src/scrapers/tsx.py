import requests
import feedparser

class TSXScraper:
    """Dedicated scraper for TSX and Canadian newswire feeds."""
    
    @staticmethod
    def get_latest_articles(rss_url=None):
        print("[TSX SCRAPER] Polling Canadian exchange feeds...")
        target_url = rss_url or "https://www.tsx.com/news/rss"
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