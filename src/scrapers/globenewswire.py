import requests
from src.scrapers.client import get_session

from bs4 import BeautifulSoup
import feedparser

from src.scrapers.base import SourceScraper
from src.config.settings import USER_AGENT

class GlobeNewswireScraper(SourceScraper):
    RSS_URL = "https://www.globenewswire.com/RssFeed/country/US/feedTitle/GlobeNewswire%20-%20US%20News"

    def get_latest_articles(self, **kwargs):
        import time
        headers = {"User-Agent": USER_AGENT}
        articles = []
        seen_ids = set()
        checkpoint = kwargs.get("checkpoint")
        self.scrape_metadata = {
            "pages_visited": 0,
            "page_limit": 5,
            "checkpoint_found": False,
            "emergency_stop": False,
            "reason": ""
        }
        
        last_page_urls = set()
        
        for page in range(1, 6):
            self.scrape_metadata["pages_visited"] = page
            url = f"https://www.globenewswire.com/NewsRoom?page={page}"
            try:
                response = get_session().get(url, headers=headers, timeout=15)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
                
                article_links = [a for a in soup.select("a") if 'href' in a.attrs and '/news-release/' in a['href']]
                if not article_links:
                    break
                    
                current_page_urls = set()
                new_articles_on_page = 0
                for a_tag in article_links:
                    href = a_tag.get('href')
                    if not href:
                        continue
                        
                    full_url = href if href.startswith("http") else "https://www.globenewswire.com" + href
                    current_page_urls.add(full_url)
                    if checkpoint and (full_url == checkpoint or href == checkpoint):
                        self.scrape_metadata["checkpoint_found"] = True
                        return articles
                    
                    # Use the path as the unique ID to avoid language-code collisions
                    article_id = href if not href.startswith("http") else full_url.replace("https://www.globenewswire.com", "")
                    
                    if article_id in seen_ids:
                        continue
                    seen_ids.add(article_id)
                    
                    # Attempt to find the publish date near the link
                    time_elem = None
                    parent = a_tag.find_parent(class_=lambda c: c and ('item' in c.lower() or 'article' in c.lower() or 'row' in c.lower()))
                    if parent:
                        time_elem = parent.find('time') or parent.find(class_=lambda c: c and 'date' in c.lower())
                    
                    if not time_elem:
                        # Fallback to nearest elements if no clear parent container
                        time_elem = a_tag.find_previous('time') or a_tag.find_next('time')
                        
                    published = ""
                    if time_elem:
                        published = time_elem.get('datetime') or time_elem.get_text(strip=True)
                    
                    articles.append({
                        "id": article_id,
                        "title": a_tag.get_text(strip=True),
                        "url": full_url,
                        "published": published
                    })
                    new_articles_on_page += 1
                    
                    if len(articles) >= 20000:
                        self.scrape_metadata["emergency_stop"] = True
                        self.scrape_metadata["reason"] = "Hit 20000 article limit"
                        print(f"[CRITICAL] GlobeNewswire hit emergency 20,000 article limit!")
                        return articles
                    
                if current_page_urls and current_page_urls == last_page_urls:
                    print(f"[INFO] GlobeNewswire detected duplicate page content on page {page}. Breaking.")
                    break
                last_page_urls = current_page_urls

                if new_articles_on_page == 0:
                    break
                    
                if not checkpoint:
                    print("[INFO] GlobeNewswire first-run (no checkpoint). Stopping after page 1.")
                    break
                    
                time.sleep(1)
            except Exception as e:
                self.scrape_metadata["reason"] = f"HTTP/Parsing Error on page {page}"
                print(f"[WARNING] GlobeNewswire pagination failed on page {page}: {e}")
                break
                
        if page == 5 and not self.scrape_metadata.get("checkpoint_found") and checkpoint:
            self.scrape_metadata["emergency_stop"] = True
            self.scrape_metadata["reason"] = "Hit 5 page limit"
            print("[CRITICAL] GlobeNewswire hit emergency 5 page limit without finding checkpoint.")
        return articles

    def get_article_body(self, url):
        headers = {"User-Agent": USER_AGENT}
        response = get_session().get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        
        # GlobeNewswire specific selectors
        article = soup.select_one("div.article-body") or soup.select_one("main")
        
        if article:
            text = article.get_text("\n", strip=True)
            if len(text) > 500:
                return text
        return None
