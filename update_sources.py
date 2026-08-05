from src.config.settings import SHEET_URL
from src.sheets import get_client
import gspread

client = get_client()
doc = client.open_by_url(SHEET_URL)
sheet = doc.worksheet("Sources")

headers = sheet.row_values(1)

# Ensure "RSS URL" and "HTML URL" exist in headers
if "RSS URL" not in headers:
    # Let's replace 'Type' (index 13) with 'RSS URL'
    if "Type" in headers:
        type_idx = headers.index("Type")
        sheet.update_cell(1, type_idx + 1, "RSS URL")
        headers[type_idx] = "RSS URL"
    else:
        # Just append it
        headers.append("RSS URL")
        sheet.update_cell(1, len(headers), "RSS URL")

if "HTML URL" not in headers:
    headers.append("HTML URL")
    sheet.update_cell(1, len(headers), "HTML URL")
    
rss_idx = headers.index("RSS URL")
html_idx = headers.index("HTML URL")
source_idx = headers.index("Source")

# Define target URLs for the main ones
target_urls = {
    "PR Newswire": {
        "rss": "https://www.prnewswire.com/rss/news-releases-list.rss",
        "html": "https://www.prnewswire.com/news-releases/"
    },
    "GlobeNewswire": {
        "rss": "https://www.globenewswire.com/RssFeed/industry/9000-Finance/feed/iso",
        "html": "https://www.globenewswire.com/NewsRoom"
    },
    "Business Wire": {
        "rss": "https://feed.businesswire.com/rss/home/?rss=G1QFDERJXkJeGVtYXw==",
        "html": "https://www.businesswire.com/portal/site/home/news/"
    },
    "SEC Edgar": {
        "rss": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&output=atom",
        "html": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent"
    },
    "GlobeNewswire_EU": {
        "rss": "https://www.globenewswire.com/RssFeed/subjectcode/31-Regulatory%20Filings/feed/iso",
        "html": "https://www.globenewswire.com/NewsRoom"
    },
    "SEC EDGAR - Schedule 13D (Activism)": {
        "rss": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=13D&output=atom",
        "html": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=13D"
    },
    "SEC EDGAR - Form 10 (Spin-Offs)": {
        "rss": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=10-12B&output=atom",
        "html": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=10-12B"
    },
    "TSX News": {
        "rss": "",
        "html": "https://money.tmx.com/en/news"
    },
    "ASX": {
        "rss": "",
        "html": "https://www.asx.com.au/asx/statistics/todayAnns.do"
    },
    "SEDAR+": {
        "rss": "",
        "html": "https://www.sedarplus.ca/csa-party/records/document.html"
    },
    "Canadian Newswire SEDAR Feeds": {
        "rss": "https://www.newswire.ca/rss/SEDAR-filings.xml",
        "html": "https://www.newswire.ca/news-releases/"
    },
    "EQS News (Germany)": {
        "rss": "https://www.eqs-news.com/rss/",
        "html": "https://www.eqs-news.com/news"
    },
    "eMarket SDIR (Italy)": {
        "rss": "",
        "html": "https://www.emarketstorage.it/en/news"
    },
    "AMF (France)": {
        "rss": "https://www.amf-france.org/fr/flux-rss/display/23",
        "html": "https://www.amf-france.org/en/news-publications/news-releases"
    },
    "CNMV (Spain)": {
        "rss": "https://www.cnmv.es/Portal/RSS/Rss.aspx?tipo=HR",
        "html": "https://www.cnmv.es/Portal/HR/ResultadoBusquedaHR.aspx"
    },
    "Finansinspektionen (Sweden)": {
        "rss": "https://www.fi.se/sv/publicerat/pressmeddelanden/rss/",
        "html": "https://www.fi.se/en/published/press-releases/"
    },
    "NewsWeb (Norway)": {
        "rss": "https://newsweb.oslobors.no/rss",
        "html": "https://newsweb.oslobors.no/search"
    },
    "AFM (Netherlands)": {
        "rss": "https://www.afm.nl/en/nieuws/rss",
        "html": "https://www.afm.nl/en/nieuws"
    },
    "SIX Exchange (Switzerland)": {
        "rss": "https://www.six-group.com/exchanges/rss/market_news_en.xml",
        "html": "https://www.six-group.com/en/market-data/news-tools/market-news.html"
    }
}

records = sheet.get_all_values()
updates = []

for row_idx, row in enumerate(records):
    if row_idx == 0:
        continue
    source_name = row[source_idx] if source_idx < len(row) else ""
    if source_name in target_urls:
        t = target_urls[source_name]
        
        # Pad row if needed
        while len(row) <= max(rss_idx, html_idx):
            row.append("")
            
        row[rss_idx] = t["rss"]
        row[html_idx] = t["html"]
        
        # Add to batch update
        # 1-indexed for gspread
        updates.append({
            'range': f"{gspread.utils.rowcol_to_a1(row_idx + 1, rss_idx + 1)}",
            'values': [[t["rss"]]]
        })
        updates.append({
            'range': f"{gspread.utils.rowcol_to_a1(row_idx + 1, html_idx + 1)}",
            'values': [[t["html"]]]
        })

print(f"Applying {len(updates)} updates...")
if updates:
    sheet.batch_update(updates)
print("Done.")

