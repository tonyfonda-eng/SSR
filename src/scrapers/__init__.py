from .businesswire import BusinessWireScraper
from .globenewswire import GlobeNewswireScraper
from .edgar import EdgarScraper, Edgar13DScraper, EdgarForm10Scraper, EdgarTenderOfferScraper, Edgar14D9Scraper, EdgarMergerProxyScraper, EdgarDefinitiveProxyScraper, EdgarS4Scraper
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
    "SEC EDGAR - Tender Offers (SC TO)": EdgarTenderOfferScraper,
    "SEC EDGAR - Board Rec (14D-9)": Edgar14D9Scraper,
    "SEC EDGAR - Merger Proxy (PREM14A)": EdgarMergerProxyScraper,
    "SEC EDGAR - Definitive Proxy (DEFM14A)": EdgarDefinitiveProxyScraper,
    "SEC EDGAR - S-4 (Stock Mergers)": EdgarS4Scraper,
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
