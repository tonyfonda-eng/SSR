import hashlib
import time
from datetime import datetime
from bs4 import BeautifulSoup
from curl_cffi import requests

from src.scrapers.base import SourceScraper

class LSECoukScraper(SourceScraper):
    """
    LSE.co.uk Native Bot Scraper.
    Uses curl_cffi to bypass Cloudflare and targets the real-time AJAX feed.
    Hashes URL strictly to prevent DOM-based deduplication lockups.
    """
    
    # Primary target
    AJAX_URL = "https://www.lse.co.uk/ajax/news/market-news-list/"
    # Fallback target
    FALLBACK_URL = "https://www.lse.co.uk/news/"
    
    def get_latest_articles(self, **kwargs):
        articles = []
        seen = set()
        
        try:
            # 1. Try the primary AJAX endpoint
            response = requests.get(self.AJAX_URL, impersonate="chrome120", timeout=8)
            
            if response.status_code == 200 and len(response.text) > 1000:
                soup = BeautifulSoup(response.text, "html.parser")
                
                for row in soup.select("li"):
                    link_tag = row.find("a")
                    if not link_tag:
                        continue
                        
                    headline = link_tag.get_text(strip=True)
                    relative_url = link_tag.get("href")
                    if relative_url:
                        full_url = f"https://www.lse.co.uk{relative_url}" if relative_url.startswith("/") else relative_url
                    else:
                        continue
                        
                    # Hash strictly the URL to create dedupe baseline
                    dedupe_hash = hashlib.md5(full_url.encode()).hexdigest()
                    
                    if dedupe_hash not in seen:
                        seen.add(dedupe_hash)
                        articles.append({
                            "id": dedupe_hash,
                            "title": headline,
                            "url": full_url,
                            "published": datetime.utcnow().isoformat()
                        })
            
            # 2. If AJAX endpoint failed or returned empty (e.g. 404), seamlessly fallback to main landing page
            if not articles:
                response = requests.get(self.FALLBACK_URL, impersonate="chrome120", timeout=8)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, "html.parser")
                    
                    # The main page uses .news__block
                    for block in soup.select('.news__block'):
                        headline_tag = block.find('h3')
                        if not headline_tag:
                            continue
                            
                        headline = headline_tag.get_text(strip=True)
                        link_tag = block.find('a')
                        
                        relative_url = link_tag.get("href") if link_tag else ""
                        if relative_url:
                            full_url = f"https://www.lse.co.uk{relative_url}" if relative_url.startswith("/") else relative_url
                        else:
                            continue
                            
                        dedupe_hash = hashlib.md5(full_url.encode()).hexdigest()
                        
                        if dedupe_hash not in seen:
                            seen.add(dedupe_hash)
                            articles.append({
                                "id": dedupe_hash,
                                "title": headline,
                                "url": full_url,
                                "published": datetime.utcnow().isoformat()
                            })
                            
        except Exception as e:
            print(f"[ERROR] LSE.co.uk Scraper failed: {e}")
            
        print(f"    [LSE.co.uk] Total unique articles fetched: {len(articles)}")
        return articles

    def get_article_body(self, url):
        """
        Uses curl_cffi to scrape the article body from lse.co.uk
        """
        try:
            response = requests.get(url, impersonate="chrome120", timeout=8)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                
                # Usually lse.co.uk articles are in an article tag or a div class news__article
                article_container = soup.find('article') or soup.find('div', class_='news__article') or soup.find('div', class_='news-article-content')
                
                if article_container:
                    # Remove scripts and styles
                    for element in article_container(["script", "style", "nav", "header", "footer"]):
                        element.decompose()
                    
                    text = article_container.get_text(separator="\n", strip=True)
                    if len(text) > 100:
                        return text
                        
                # Fallback to general page text if specific container not found
                for element in soup(["script", "style", "nav", "header", "footer"]):
                    element.decompose()
                return soup.get_text(separator="\n", strip=True)
                
        except Exception as e:
            print(f"[WARNING] Failed to fetch LSE.co.uk article body: {e}")
            
        return "[LSE.co.uk] Classify event based on Title."
