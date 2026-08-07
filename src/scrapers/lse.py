import json
import time
from datetime import datetime
from src.scrapers.base import SourceScraper

class LSEScraper(SourceScraper):
    """
    London Stock Exchange Scraper using Playwright.
    Bypasses Cloudflare protection to fetch exact Special Situations RNS announcements.
    """
    
    BASE_URL = "https://www.londonstockexchange.com/news?tab=news-explorer&excludeheadlines=&headlinetypes=&headlines=151,33,32,37,36,35,34,144,155,154"
    
    def get_latest_articles(self, **kwargs):
        articles = []
        seen = set()
        
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            print("[ERROR] Playwright not installed. Skipping LSE scraper.")
            return articles
            
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
                )
                
                # We want to capture the JSON API response the frontend makes
                api_responses = []
                
                def handle_response(response):
                    if "api/v1/components/refresh" in response.url or "api/gw/lse/news" in response.url:
                        if response.status == 200:
                            try:
                                api_responses.append(response.json())
                            except:
                                pass
                                
                page.on("response", handle_response)
                
                print("[LSE] Navigating to London Stock Exchange News Explorer...")
                page.goto(self.BASE_URL, wait_until="networkidle", timeout=25000)
                
                # Give it a second to parse responses
                time.sleep(2)
                
                news_items = []
                # First try to extract from intercepted API responses
                for data in api_responses:
                    try:
                        if isinstance(data, list) and len(data) > 0 and 'content' in data[0]:
                            content = data[0]['content']
                            for c in content:
                                if c.get('name') == 'results' and isinstance(c.get('value'), list):
                                    news_items.extend(c['value'])
                    except Exception as e:
                        pass
                
                # If API interception failed (e.g., cached or different structure), parse the rendered DOM
                if not news_items:
                    print("[LSE] API interception yielded no results. Parsing rendered DOM...")
                    rows = page.query_selector_all("tr.news-table__row")
                    for row in rows:
                        try:
                            # Usually inside <td class="news-table__td news-table__headline"> -> <a>
                            link_elem = row.query_selector("td.news-table__headline a")
                            if link_elem:
                                title = link_elem.inner_text().strip()
                                href = link_elem.get_attribute("href")
                                url = f"https://www.londonstockexchange.com{href}" if href.startswith("/") else href
                                
                                # Make up a unique ID from the URL
                                article_id = url.split('/')[-1] if '/' in url else url
                                
                                if article_id and article_id not in seen:
                                    seen.add(article_id)
                                    articles.append({
                                        "id": article_id,
                                        "title": title,
                                        "url": url,
                                        "published": datetime.utcnow().isoformat()
                                    })
                        except Exception as e:
                            pass
                else:
                    print("[LSE] Extracted articles from intercepted API payload.")
                    for item in news_items:
                        article_id = item.get("id", "")
                        title = item.get("headline", "")
                        news_url = item.get("newsurl", "")
                        url = f"https://www.londonstockexchange.com{news_url}" if news_url.startswith("/") else news_url
                        
                        if article_id and article_id not in seen:
                            seen.add(article_id)
                            articles.append({
                                "id": str(article_id),
                                "title": title,
                                "url": url,
                                "published": item.get("datetime", "")
                            })
                            
                browser.close()
                
        except Exception as e:
            print(f"[ERROR] LSE Scraper failed: {e}")
            
        print(f"    [LSE] Total unique articles fetched: {len(articles)}")
        return articles

    def get_article_body(self, url):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return None
            
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
                )
                
                page.goto(url, wait_until="networkidle", timeout=20000)
                
                # The news article body is usually in an article tag or specific div
                content = page.query_selector("div.news-article-content")
                if not content:
                    content = page.query_selector("div#news-article-content")
                if not content:
                    content = page.query_selector("article")
                    
                text = content.inner_text() if content else page.evaluate("document.body.innerText")
                
                browser.close()
                
                if text and len(text) > 100:
                    return text
                    
        except Exception as e:
            print(f"[WARNING] Failed to fetch LSE article body via Playwright: {e}")
            
        return None