class SourceScraper:
    def __init__(self):
        pass

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
