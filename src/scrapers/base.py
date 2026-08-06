class SourceScraper:
    def __init__(self):
        self.scrape_metadata = {
            "pages_visited": 0,
            "page_limit": 0,
            "checkpoint_found": False,
            "emergency_stop": False,
            "reason": ""
        }

    def get_latest_articles(self, **kwargs):
        """
        Returns a list of dictionaries with keys:
        - id
        - title
        - url
        - published
        - body (optional, if fetched in bulk)
        """
        raise NotImplementedError

    def get_article_body(self, url):
        """
        Returns the text body of an article given its URL.
        """
        raise NotImplementedError
