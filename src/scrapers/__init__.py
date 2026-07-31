from .businesswire import BusinessWireScraper
from .globenewswire import GlobeNewswireScraper
from .edgar import EdgarScraper
from .edgar_items import EdgarItemScraper
from .prnewswire import PRNewsWireScraper
from .kedm import KEDMScraper
from .googlenews import GoogleNewsScraper

SCRAPER_REGISTRY = {
    "Business Wire": BusinessWireScraper,
    "GlobeNewswire": GlobeNewswireScraper,
    "SEC Edgar": EdgarScraper,
    "SEC Edgar 8-K Items": EdgarItemScraper,
    "PR Newswire": PRNewsWireScraper,
    "KEDM": KEDMScraper,
    "Google News": GoogleNewsScraper,
}

def get_scraper_for_source(source_name):
    scraper_class = SCRAPER_REGISTRY.get(source_name)
    if scraper_class:
        return scraper_class()
    return None
