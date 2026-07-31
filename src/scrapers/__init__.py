from .businesswire import BusinessWireScraper
from .globenewswire import GlobeNewswireScraper
from .edgar import EdgarScraper, Edgar13DScraper, EdgarForm10Scraper
from .edgar_items import EdgarItemScraper
from .prnewswire import PRNewsWireScraper
from .kedm import KEDMScraper
from .googlenews import GoogleNewsScraper
from .nasdaq import NasdaqScraper
from .lse import LSEScraper

SCRAPER_REGISTRY = {
    "Business Wire": BusinessWireScraper,
    "GlobeNewswire": GlobeNewswireScraper,
    "SEC Edgar": EdgarScraper,
    "SEC EDGAR - Schedule 13D (Activism)": Edgar13DScraper,
    "SEC EDGAR - Form 10 (Spin-Offs)": EdgarForm10Scraper,
    "SEC Edgar 8-K Items": EdgarItemScraper,
    "PR Newswire": PRNewsWireScraper,
    "KEDM": KEDMScraper,
    "Google News": GoogleNewsScraper,
    "Nasdaq": NasdaqScraper,
    "London Stock Exchange": LSEScraper,
}

def get_scraper_for_source(source_name):
    scraper_class = SCRAPER_REGISTRY.get(source_name)
    if scraper_class:
        return scraper_class()
    return None
