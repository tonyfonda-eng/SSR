from src.config.settings import SHEET_URL
from src.sheets import get_client
import json

def fix_sources():
    client = get_client()
    sheet = client.open_by_url(SHEET_URL)
    worksheet = sheet.worksheet("Sources")
    raw_values = worksheet.get_all_values()
    
    if not raw_values:
        return
        
    headers = raw_values[0]
    try:
        source_idx = headers.index("Source")
        regulator_idx = headers.index("Regulator")
        url_idx = headers.index("HTML URL")
        status_idx = headers.index("Status")
        enabled_idx = headers.index("Enabled")
        type_idx = headers.index("Type")
    except ValueError as e:
        print(f"Missing header: {e}")
        return
        
    for i in range(1, len(raw_values)):
        row = raw_values[i]
        # pad row if needed
        row += [""] * (len(headers) - len(row))
        
        source_name = row[source_idx].strip()
        reg = row[regulator_idx].strip()
        url = row[url_idx].strip()
        
        # 1. Move URL from Regulator
        if reg.startswith("http") and not url:
            row[url_idx] = reg
            row[regulator_idx] = ""
            row[type_idx] = "RSS" if "rss" in reg.lower() or "atom" in reg.lower() or "xml" in reg.lower() else "HTML"
            
        # 2. Pre-fill GlobeNewswire and Business Wire
        if "GlobeNewswire" == source_name:
            row[url_idx] = "https://www.globenewswire.com/RssFeed/industry/9000-Finance/feed/iso"
            row[type_idx] = "RSS"
        elif "Business Wire" == source_name:
            row[url_idx] = "https://feed.businesswire.com/rss/home/?rss=G1QFDERJXkJeGVtYXw=="
            row[type_idx] = "RSS"
            
        # 3. Enable and set status active for ALL rows that have a source name
        if source_name:
            row[status_idx] = "Active"
            row[enabled_idx] = "TRUE"
            
        raw_values[i] = row
        
    # Update back to sheets
    worksheet.update("A1", raw_values)
    print("Successfully formatted and updated the Sources tab!")

if __name__ == "__main__":
    fix_sources()
