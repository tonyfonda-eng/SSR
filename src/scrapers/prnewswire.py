"""
Downloads and extracts PR Newswire articles.
"""

import requests
from bs4 import BeautifulSoup

from src.config import USER_AGENT
from src.scrapers.base import SourceScraper


def download_article(url):

    headers = {
        "User-Agent": USER_AGENT
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=30,
    )

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Try several possible article containers
    selectors = [
        "div.release-body",
        "div.release-text",
        "div.article-body",
        "div[data-module='ArticleBody']",
        "article"
    ]

    for selector in selectors:

        article = soup.select_one(selector)

        if article:

            text = article.get_text("\n", strip=True)

            # Ignore obviously bad extractions
            if len(text) > 1000:
                return text

    return None


class PRNewsWireScraper(SourceScraper):
    def get_latest_articles(self):
        import time
        headers = {
            "User-Agent": USER_AGENT
        }
        
        articles = []
        # Fetch 3 pages of 100 articles each = 300 articles per run
        for page in range(1, 4):
            url = f"https://www.prnewswire.com/news-releases/news-releases-list/?page={page}&pagesize=100"
            
            try:
                response = requests.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, "html.parser")
                
                # PR Newswire news release cards
                article_links = soup.select('.news-release') or soup.select('.card h3 a') or soup.select('.row.newsCards a')
                
                if not article_links:
                    break # No more articles found, stop pagination
                    
                for a_tag in article_links:
                    href = a_tag.get('href')
                    if not href:
                        continue
                    
                    full_url = href if href.startswith("http") else "https://www.prnewswire.com" + href
                    article_id = full_url.rstrip("/").split("-")[-1].replace(".html", "")
                    
                    articles.append({
                        "id": article_id,
                        "title": a_tag.get_text(strip=True),
                        "url": full_url,
                        "published": ""  # Could be parsed from HTML, but keep simple for now
                    })
                    
                time.sleep(1) # Be polite to their server between pagination requests
                
            except Exception as e:
                print(f"[WARNING] PR Newswire pagination failed on page {page}: {e}")
                break
                
        return articles
    def get_article_body(self, url):
        return download_article(url)
