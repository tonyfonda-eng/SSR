from src.scrapers.globenewswire import GlobeNewswireScraper
import time

s = GlobeNewswireScraper()
print("Fetching latest articles (list)...")
t0 = time.time()
articles = s.get_latest_articles()
print(f"Fetched {len(articles)} articles in {time.time() - t0:.2f}s")
