import sys
import logging
logging.basicConfig(level=logging.INFO)

from src.scrapers.prnewswire import PRNewsWireScraper
from src.scrapers.businesswire import BusinessWireScraper
import json

def test_pr_newswire():
    print("Testing PR Newswire backfill...")
    scraper = PRNewsWireScraper()
    # Fake checkpoint to trigger full 2000 article HTML backfill
    articles = scraper.get_latest_articles(checkpoint="https://www.prnewswire.com/news-releases/fake.html")
    
    found_bzh = False
    found_dv = False
    found_jwel = False
    
    for a in articles:
        title = a.get("title", "").lower()
        if "beazer" in title or "bzh" in title:
            print(f"[FOUND BZH] PRN: {title}")
            found_bzh = True
        if "doubleverify" in title or " dv " in title:
            print(f"[FOUND DV] PRN: {title}")
            found_dv = True
        if "jamieson" in title or "jwel" in title:
            print(f"[FOUND JWEL] PRN: {title}")
            found_jwel = True
            
    return found_bzh, found_dv, found_jwel

def test_business_wire():
    print("Testing Business Wire backfill (limited to RSS)...")
    # For Business Wire, we can't backfill via HTML, but we can check if it's in the latest RSS feeds
    scraper = BusinessWireScraper()
    articles = scraper.get_latest_articles()
    
    found_bzh = False
    found_dv = False
    found_jwel = False
    
    for a in articles:
        title = a.get("title", "").lower()
        if "beazer" in title or "bzh" in title:
            print(f"[FOUND BZH] BW: {title}")
            found_bzh = True
        if "doubleverify" in title or " dv " in title:
            print(f"[FOUND DV] BW: {title}")
            found_dv = True
        if "jamieson" in title or "jwel" in title:
            print(f"[FOUND JWEL] BW: {title}")
            found_jwel = True
            
    return found_bzh, found_dv, found_jwel

if __name__ == "__main__":
    test_pr_newswire()
    test_business_wire()
