from src.scrapers.googlenews import GoogleNewsScraper

class EQSScraper(GoogleNewsScraper):
    """Germany / DACH region OAM"""
    def __init__(self):
        super().__init__()
        self.query = 'site:eqs-news.com/news/ "ad-hoc"'
        self.document_type = 'Ad-hoc'

class BorsaItalianaScraper(GoogleNewsScraper):
    """Italy OAM (eMarket SDIR / Teleborsa)"""
    def __init__(self):
        super().__init__()
        self.query = 'site:emarketstorage.it OR site:emarketstorage.com "price sensitive" OR "regulated information"'
        self.document_type = 'Price Sensitive'

class AMFScraper(GoogleNewsScraper):
    """France OAM"""
    def __init__(self):
        super().__init__()
        self.query = 'site:amf-france.org "information réglementée"'
        self.document_type = 'Regulated Information'

class CNMVScraper(GoogleNewsScraper):
    """Spain OAM (Hechos Relevantes)"""
    def __init__(self):
        super().__init__()
        self.query = 'site:cnmv.es/Portal/HR/ "información privilegiada" OR "otra información relevante"'
        self.document_type = 'Información Privilegiada'

class FIScraper(GoogleNewsScraper):
    """Sweden OAM (Finansinspektionen)"""
    def __init__(self):
        super().__init__()
        self.query = 'site:fi.se "insider information"'
        self.document_type = 'Regulatory'

class NewsWebScraper(GoogleNewsScraper):
    """Norway OAM (Oslo Børs)"""
    def __init__(self):
        super().__init__()
        self.query = 'site:newsweb.oslobors.no/message/ "mandatory notification"'
        self.document_type = 'Inside Information'

class AFMScraper(GoogleNewsScraper):
    """Netherlands OAM (Autoriteit Financiële Markten)"""
    def __init__(self):
        super().__init__()
        self.query = 'site:afm.nl/en/professionals/registers/meldingen-marktmisbruik "inside information"'
        self.document_type = 'Inside Information'

class SIXScraper(GoogleNewsScraper):
    """Switzerland OAM (SIX Exchange)"""
    def __init__(self):
        super().__init__()
        self.query = 'site:ser-ag.com/en/resources/notifications-market-participants/ "ad hoc announcement"'
        self.document_type = 'Ad-hoc'
