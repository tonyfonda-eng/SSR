from .businesswire import BusinessWireScraper
from .globenewswire import GlobeNewswireScraper
from .edgar import EdgarScraper

SCRAPER_REGISTRY = {
    "Business Wire": BusinessWireScraper,
    "GlobeNewswire": GlobeNewswireScraper,
    "SEC Edgar": EdgarScraper,
}

def get_scraper_for_source(source_name):
    scraper_class = SCRAPER_REGISTRY.get(source_name)
    if scraper_class:
        return scraper_class()
    return None
