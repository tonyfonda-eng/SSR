import requests
from bs4 import BeautifulSoup
import feedparser

from src.scrapers.base import SourceScraper
from src.config.settings import USER_AGENT

class BusinessWireScraper(SourceScraper):
    """
    BusinessWire scraper using multi-category RSS feeds.
    HTML pagination is permanently 403-blocked from cloud/CI server IPs,
    so RSS is the primary and only viable ingestion method.
    """

    # Each feed returns ~20-30 articles. We merge and deduplicate across categories.
    RSS_FEEDS = [
        ("Global News",       "https://feed.businesswire.com/rss/home/?rss=G1QFDERJXkJeGVtQWA%3D%3D"),
        ("M&A",               "https://feed.businesswire.com/rss/home/?rss=G1QFDERJXkJeGVtQXA%3D%3D"),
        ("Earnings",          "https://feed.businesswire.com/rss/home/?rss=G1QFDERJXkJeGVtQXg%3D%3D"),
        ("Technology",        "https://feed.businesswire.com/rss/home/?rss=G1QFDERJXkJeGVtQWw%3D%3D"),
        ("Healthcare",        "https://feed.businesswire.com/rss/home/?rss=G1QFDERJXkJeGVtQWg%3D%3D"),
        ("Financial Services","https://feed.businesswire.com/rss/home/?rss=G1QFDERJXkJeGVtRWA%3D%3D"),
        ("Banking",           "https://feed.businesswire.com/rss/home/?rss=G1QFDERJXkJeGVtRXg%3D%3D"),
        ("Real Estate",       "https://feed.businesswire.com/rss/home/?rss=G1QFDERJXkJeGVtRXA%3D%3D"),
        ("Regulatory",        "https://feed.businesswire.com/rss/home/?rss=G1QFDERJXkJeGVtRWQ%3D%3D"),
        ("Venture Capital",   "https://feed.businesswire.com/rss/home/?rss=G1QFDERJXkJeGVtRWg%3D%3D"),
    ]

    def _extract_article_id(self, url):
        """Extract a stable article ID from a BusinessWire URL."""
        # BusinessWire URLs: .../news/home/20260731332753/en/Title-Slug
        parts = url.rstrip("/").split("/")
        # The numeric ID is typically the second-to-last segment before /en/
        for i, part in enumerate(parts):
            if part.isdigit() and len(part) >= 10:
                return part
        # Fallback: use the second-to-last path segment
        return parts[-2] if len(parts) > 2 else url

    def get_latest_articles(self, **kwargs):
        import time
        articles = []
        seen_ids = set()

        for category_name, feed_url in self.RSS_FEEDS:
            try:
                # Fetch with requests to enforce timeout and avoid feedparser hangs
                headers = {"User-Agent": USER_AGENT}
                response = requests.get(feed_url, headers=headers, timeout=15)
                response.raise_for_status()
                feed = feedparser.parse(response.content)
                new_in_feed = 0
                for entry in feed.entries:
                    article_id = self._extract_article_id(entry.link)

                    if article_id not in seen_ids:
                        seen_ids.add(article_id)
                        # Strip feedref tracking params from URL
                        clean_url = entry.link.split("?feedref=")[0]
                        articles.append({
                            "id": article_id,
                            "title": entry.title,
                            "url": clean_url,
                            "published": getattr(entry, "published", "")
                        })
                        new_in_feed += 1

                if new_in_feed > 0:
                    print(f"    [BW RSS] {category_name}: {new_in_feed} unique articles")
            except Exception as e:
                print(f"[WARNING] BusinessWire RSS feed '{category_name}' failed: {e}")

            time.sleep(0.5)  # Be polite between feed requests

        print(f"    [BW RSS] Total unique articles: {len(articles)}")
        return articles

    def get_article_body(self, url):
        headers = {"User-Agent": USER_AGENT}
        try:
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, "html.parser")

            # Business Wire specific selectors
            article = soup.select_one("div.bw-release-story") or soup.select_one("main")

            if article:
                text = article.get_text("\n", strip=True)
                if len(text) > 500:
                    return text
        except Exception as e:
            print(f"[WARNING] Failed to fetch BusinessWire article body: {e}")
        return None

