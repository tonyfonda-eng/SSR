from src.scrapers.googlenews import GoogleNewsScraper

class EQSScraper(GoogleNewsScraper):
    """Germany / DACH region OAM"""
    def __init__(self):
        super().__init__()
        self.query = 'site:eqs-news.com "ad-hoc" OR "corporate news"'

class ActusnewsScraper(GoogleNewsScraper):
    """France OAM"""
    def __init__(self):
        super().__init__()
        self.query = 'site:actusnews.com/en/ "regulated information" OR "press release"'

class CNMVScraper(GoogleNewsScraper):
    """Spain OAM (Hechos Relevantes)"""
    def __init__(self):
        super().__init__()
        # OAM announcements in English or Spanish
        self.query = 'site:cnmv.es "inside information" OR "other relevant information" OR "información privilegiada" OR "otra información relevante"'

class BorsaItalianaScraper(GoogleNewsScraper):
    """Italy OAM (eMarket SDIR / Teleborsa)"""
    def __init__(self):
        super().__init__()
        self.query = 'site:emarketstorage.it OR site:emarketstorage.com "price sensitive" OR "regulated information"'

class EuronextScraper(GoogleNewsScraper):
    """Netherlands / Pan-European Exchange"""
    def __init__(self):
        super().__init__()
        self.query = 'site:live.euronext.com/en/product/equities "company news" OR "press release"'
