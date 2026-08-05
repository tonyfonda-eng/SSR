from src.scrapers.prnewswire import PRNewsWireScraper
scraper = PRNewsWireScraper()
body = scraper.get_article_body("https://www.prnewswire.com/news-releases/amc-entertainment-holdings-inc-reports-second-quarter-2024-results-302213753.html")
print("Body length:", len(body) if body else 0)
