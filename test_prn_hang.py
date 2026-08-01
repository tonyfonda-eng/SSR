from src.scrapers.prnewswire import PRNewsWireScraper
import time

s = PRNewsWireScraper()
print("Fetching latest articles (list)...")
t0 = time.time()
articles = s.get_latest_articles()
print(f"Fetched {len(articles)} articles in {time.time() - t0:.2f}s")

for i, a in enumerate(articles[:5]):
    print(f"Fetching body {i+1} - {a['url']}")
    t1 = time.time()
    body = s.get_article_body(a['url'])
    print(f"Body size: {len(body) if body else 0} in {time.time() - t1:.2f}s")
