from .businesswire import BusinessWireScraper
from .globenewswire import GlobeNewswireScraper
from .edgar import EdgarScraper
from .prnewswire import PRNewsWireScraper
import src.scrapers.kedm as kedm

SCRAPER_REGISTRY = {
    "Business Wire": BusinessWireScraper,
    "GlobeNewswire": GlobeNewswireScraper,
    "SEC Edgar": EdgarScraper,
    "PR Newswire": PRNewsWireScraper,
    "KEDM": kedm,
}

def get_scraper_for_source(source_name):
    scraper_class = SCRAPER_REGISTRY.get(source_name)
    if scraper_class:
        return scraper_class()
    return None
