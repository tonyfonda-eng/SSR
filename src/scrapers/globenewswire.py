import requests
# --- WAF BYPASS WRAPPER ---
try:
    import requests
    _orig_get = requests.get
    def _spoofed_get(*args, **kwargs):
        headers = kwargs.get('headers', {})
        if isinstance(headers, dict) and 'User-Agent' not in headers:
            headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        kwargs['headers'] = headers
        return _orig_get(*args, **kwargs)
    requests.get = _spoofed_get
except ImportError:
    pass
# --------------------------

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
        
        for page in range(1, 201):
            url = f"https://www.globenewswire.com/NewsRoom?page={page}"
            try:
                response = requests.get(url, headers=headers, timeout=15)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
                
                article_links = [a for a in soup.select("a") if 'href' in a.attrs and '/news-release/' in a['href']]
                if not article_links:
                    break
                    
                for a_tag in article_links:
                    href = a_tag.get('href')
                    if not href:
                        continue
                        
                    full_url = href if href.startswith("http") else "https://www.globenewswire.com" + href
                    if checkpoint and (full_url == checkpoint or href == checkpoint):
                        return articles
                    
                    # Use the path as the unique ID to avoid language-code collisions
                    article_id = href if not href.startswith("http") else full_url.replace("https://www.globenewswire.com", "")
                    
                    if article_id in seen_ids:
                        continue
                    seen_ids.add(article_id)
                    
                    articles.append({
                        "id": article_id,
                        "title": a_tag.get_text(strip=True),
                        "url": full_url,
                        "published": ""
                    })
                    
                    if len(articles) >= 20000:
                        print(f"[CRITICAL] GlobeNewswire hit emergency 20,000 article limit!")
                        return articles
                    
                time.sleep(1)
            except Exception as e:
                print(f"[WARNING] GlobeNewswire pagination failed on page {page}: {e}")
                break
                
        if page == 200:
            print("[CRITICAL] GlobeNewswire hit emergency 200 page limit without finding checkpoint.")
        return articles

    def get_article_body(self, url):
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(url, headers=headers, timeout=15)
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
