import requests
from xml.etree import ElementTree as ET
from urllib.parse import urlparse
from src.scrapers.base import SourceScraper
from src.config.settings import USER_AGENT

class ReutersScraper(SourceScraper):
    """
    Reuters Scraper using the Arc Publishing News Sitemap.
    Bypasses Cloudflare PerimeterX by avoiding the HTML and polling the live XML feed.
    """
    
    SITEMAP_URL = "https://www.reuters.com/arc/outboundfeeds/news-sitemap/?outputType=xml"
    
    def get_latest_articles(self, **kwargs):
        headers = {"User-Agent": USER_AGENT}
        articles = []
        seen = set()
        
        try:
            # Tuple timeout: (3s connect limit, 5s read limit)
            response = requests.get(self.SITEMAP_URL, headers=headers, timeout=(3.0, 5.0))
            response.raise_for_status()
            
            # The XML uses namespaces
            namespaces = {
                'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9',
                'news': 'http://www.google.com/schemas/sitemap-news/0.9'
            }
            
            root = ET.fromstring(response.text)
            
            for url_node in root.findall('sm:url', namespaces):
                loc_node = url_node.find('sm:loc', namespaces)
                if loc_node is None or not loc_node.text:
                    continue
                    
                url = loc_node.text
                
                # Check for explicit news title if available
                title = None
                news_node = url_node.find('news:news', namespaces)
                if news_node is not None:
                    title_node = news_node.find('news:title', namespaces)
                    if title_node is not None and title_node.text:
                        title = title_node.text
                
                # Fallback: Extract title from URL slug if no explicit title is provided
                if not title:
                    parsed = urlparse(url)
                    path_parts = [p for p in parsed.path.split('/') if p]
                    if path_parts:
                        # Usually the last part is the slug e.g., 'company-name-buys-startup-2026-08-07'
                        slug = path_parts[-1]
                        # Remove trailing dates like '-2026-08-07' using a simple heuristic
                        parts = slug.split('-')
                        if len(parts) > 3 and parts[-1].isdigit() and parts[-2].isdigit() and parts[-3].isdigit():
                            clean_slug = '-'.join(parts[:-3])
                        else:
                            clean_slug = slug
                        
                        title = clean_slug.replace('-', ' ').title()
                
                if not title:
                    title = "Reuters News Update"
                    
                # Extract timestamp
                pub_date = ""
                lastmod_node = url_node.find('sm:lastmod', namespaces)
                if lastmod_node is not None and lastmod_node.text:
                    pub_date = lastmod_node.text
                    
                article_id = url.split('/')[-2] if url.endswith('/') else url.split('/')[-1]
                
                if article_id and article_id not in seen:
                    seen.add(article_id)
                    articles.append({
                        "id": article_id,
                        "title": title,
                        "url": url,
                        "published": pub_date
                    })
                    
        except requests.exceptions.Timeout:
            print("[ERROR] Reuters Scraper timed out fetching sitemap.")
        except Exception as e:
            print(f"[ERROR] Reuters Scraper failed: {e}")
            
        print(f"    [Reuters] Total unique articles fetched: {len(articles)}")
        return articles

    def get_article_body(self, url):
        """
        Returns a fallback string. Reuters PerimeterX heavily protects article pages from headless scraping.
        The AI pipeline will rely solely on the headline/URL for evaluation.
        We must NOT return an empty string, otherwise dedupe will be poisoned by hash collisions.
        """
        return "[Reuters] Classify event based on Title."
