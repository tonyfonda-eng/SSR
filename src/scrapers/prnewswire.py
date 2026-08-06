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
        headers = {
            "User-Agent": USER_AGENT
        }
        
        articles = []
        checkpoint = kwargs.get("checkpoint")
        
        # Extended metadata as requested
        self.scrape_metadata = {
            "pages_visited": 0,
            "page_limit": 200,
            "checkpoint_found": False,
            "emergency_stop": False,
            "duplicate_page_detected": False,
            "http_failures": 0,
            "reason": "",
            "last_checkpoint_url": checkpoint
        }
        
        last_page_urls = set()
        
        for page in range(1, self.scrape_metadata["page_limit"] + 1):
            self.scrape_metadata["pages_visited"] = page
            # Switched from global 'news-releases-list' to 'financial-services-latest-news-list' to dramatically reduce non-deal noise
            url = f"https://www.prnewswire.com/news-releases/financial-services-latest-news/financial-services-latest-news-list/?page={page}&pagesize=100"
            
            try:
                response = get_session().get(url, headers=headers, timeout=30)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, "html.parser")
                
                # PR Newswire news release cards
                article_links = soup.select('.news-release') or soup.select('.card h3 a') or soup.select('.row.newsCards a')
                
                if not article_links:
                    self.scrape_metadata["reason"] = "No article links on page"
                    break # No more articles found, stop pagination
                    
                current_page_urls = set()
                new_articles_on_page = 0
                for a_tag in article_links:
                    href = a_tag.get('href')
                    if not href:
                        continue
                    
                    full_url = href if href.startswith("http") else "https://www.prnewswire.com" + href
                    current_page_urls.add(full_url)
                    
                    if checkpoint and (full_url == checkpoint or href == checkpoint):
                        self.scrape_metadata["checkpoint_found"] = True
                        return articles
                        
                    article_id = full_url.rstrip("/").split("-")[-1].replace(".html", "")
                    
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
                                    # Split on timezone boundaries to handle prefixes like "LONDON, Aug 6"
                                    # without breaking if layout shifts
                                    for tz in [' ET', ' PT', ' CT', ' MT', ' EST', ' PST', ' CST', ' MST']:
                                        if tz in text[:100]:
                                            parts = text.split(tz, 1)
                                            published = parts[0].strip() + tz
                                            content.replace_with(parts[1].lstrip())
                                            break
                                    if published:
                                        break
                                        
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
                    
                # Stop Condition 1: Duplicate Page Fingerprint
                if current_page_urls and current_page_urls == last_page_urls:
                    self.scrape_metadata["duplicate_page_detected"] = True
                    self.scrape_metadata["reason"] = f"Duplicate page content detected on page {page}"
                    print(f"[INFO] PR Newswire detected duplicate page content on page {page}. Breaking.")
                    break
                last_page_urls = current_page_urls
                
                # Stop Condition 2: No New URLs on Page
                if new_articles_on_page == 0:
                    self.scrape_metadata["reason"] = f"No new URLs found on page {page}"
                    break
                    
                if not checkpoint and page >= 3:
                    self.scrape_metadata["reason"] = "Initial scan complete (3 pages backfilled)"
                    print("[INFO] PR Newswire initial scan complete (3 pages backfilled). Stopping.")
                    break
                    
                time.sleep(1) # Be polite to their server between pagination requests
                
            except Exception as e:
                self.scrape_metadata["http_failures"] += 1
                self.scrape_metadata["reason"] = f"HTTP/Parsing Error on page {page}: {e}"
                print(f"[WARNING] PR Newswire pagination failed on page {page}: {e}")
                break
                
        # Stop Condition 3: Emergency Cap Hit (Graceful Degradation)
        if page == self.scrape_metadata["page_limit"] and not self.scrape_metadata.get("checkpoint_found") and checkpoint:
            self.scrape_metadata["emergency_stop"] = True
            if not self.scrape_metadata["reason"]:
                self.scrape_metadata["reason"] = f"Hit {self.scrape_metadata['page_limit']} page limit without checkpoint"
            print(f"[WARN] PR Newswire hit emergency {self.scrape_metadata['page_limit']} page limit without finding checkpoint. Returning what was collected.")
            
        return articles
        
    def get_article_body(self, url):
        return download_article(url)
