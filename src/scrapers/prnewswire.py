import re
"""
Downloads and extracts PR Newswire articles.
"""

import requests
from src.scrapers.client import get_session

from bs4 import BeautifulSoup

from src.config import USER_AGENT
from src.scrapers.base import SourceScraper


def download_article(url):

    headers = {
        "User-Agent": USER_AGENT
    }

    response = get_session().get(
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
    def get_latest_articles(self, **kwargs):
        import time
        from src.ingestion.checkpoints import get_checkpoint, set_checkpoint
        headers = {
            "User-Agent": USER_AGENT
        }
        
        articles = []
        
        self.scrape_metadata = {
            "pages_visited": 0,
            "page_limit": 200,
            "checkpoint_found": False,
            "emergency_stop": False,
            "duplicate_page_detected": False,
            "http_failures": 0,
            "reason": ""
        }
        
        CATEGORIES = [
            ("Financial", "financial-services-latest-news/financial-services-latest-news-list"),
            ("Tech", "business-technology-latest-news/business-technology-latest-news-list"),
            ("Health", "health-latest-news/health-latest-news-list"),
            ("Industrial", "heavy-industry-manufacturing-latest-news/heavy-industry-manufacturing-latest-news-list")
        ]
        
        pages_per_category = max(1, self.scrape_metadata["page_limit"] // len(CATEGORIES))
        seen_ids = set()
        
        for cat_name, cat_path in CATEGORIES:
            checkpoint = get_checkpoint("PR Newswire", f"HTML-{cat_name}")
            last_page_urls = set()
            cat_checkpoint_found = False
            first_url = None
            
            for page in range(1, pages_per_category + 1):
                self.scrape_metadata["pages_visited"] += 1
                url = f"https://www.prnewswire.com/news-releases/{cat_path}/?page={page}&pagesize=100"
                
                try:
                    response = get_session().get(url, headers=headers, timeout=30)
                    response.raise_for_status()
                    
                    soup = BeautifulSoup(response.text, "html.parser")
                    article_links = soup.select('.news-release') or soup.select('.card h3 a') or soup.select('.row.newsCards a')
                    
                    if not article_links:
                        break
                        
                    current_page_urls = set()
                    new_articles_on_page = 0
                    
                    for a_tag in article_links:
                        href = a_tag.get('href')
                        if not href: continue
                        
                        full_url = href if href.startswith("http") else "https://www.prnewswire.com" + href
                        current_page_urls.add(full_url)
                        
                        if not first_url:
                            first_url = full_url
                            
                        if checkpoint and (full_url == checkpoint or href == checkpoint):
                            cat_checkpoint_found = True
                            self.scrape_metadata["checkpoint_found"] = True
                            break
                            
                        article_id = full_url.rstrip("/").split("-")[-1].replace(".html", "")
                        
                        if article_id not in seen_ids:
                            seen_ids.add(article_id)
                            
                            title_elem = a_tag.find('h3')
                            title = ""
                            published = ""
                            if title_elem:
                                small = title_elem.find('small')
                                if small:
                                    published = small.get_text(strip=True)
                                    small.extract()
                                if not published:
                                    from bs4 import NavigableString
                                    for content in title_elem.contents:
                                        if isinstance(content, NavigableString):
                                            text = str(content)
                                            for tz in [' ET', ' PT', ' CT', ' MT', ' EST', ' PST', ' CST', ' MST']:
                                                if tz in text[:100]:
                                                    parts = text.split(tz, 1)
                                                    published = parts[0].strip() + tz
                                                    content.replace_with(parts[1].lstrip())
                                                    break
                                            if published: break
                                title = title_elem.get_text(strip=True)
                            else:
                                title = a_tag.get_text(strip=True)
                                
                            articles.append({
                                "id": article_id,
                                "title": title,
                                "url": full_url,
                                "published": published
                            })
                            new_articles_on_page += 1
                            
                    if cat_checkpoint_found:
                        break
                        
                    if current_page_urls and current_page_urls == last_page_urls:
                        self.scrape_metadata["duplicate_page_detected"] = True
                        break
                    last_page_urls = current_page_urls
                    
                    if new_articles_on_page == 0:
                        break
                        
                    if not checkpoint and page >= 3:
                        break
                        
                    time.sleep(1)
                except Exception as e:
                    self.scrape_metadata["http_failures"] += 1
                    print(f"[WARNING] PR Newswire {cat_name} page {page} failed: {e}")
                    break
                    
            if first_url:
                set_checkpoint("PR Newswire", f"HTML-{cat_name}", first_url)
                
        return articles
        
    def get_article_body(self, url):
        return download_article(url)
