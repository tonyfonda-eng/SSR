import src.sheets as sheets
import re
try:
    with open('src/sheets.py', 'r') as f:
        content = f.read()
    sheet_url_match = re.search(r'open_by_url\("([^"]+)"\)', content)
    url = sheet_url_match.group(1) if sheet_url_match else None
    
    gc = sheets.get_client()
    sh = gc.open_by_url(url)
    ws = sh.worksheet("Sources")
    headers = ws.row_values(1)
    row = []
    for header in headers:
        if header == "Source Name": row.append("London Stock Exchange")
        elif header == "Active Scraper": row.append("lse")
        elif header == "Type": row.append("HTML (Investegate RNS)")
        elif header == "Status": row.append("Active")
        elif header in ["Articles Scanned (Total)", "Confidence Over 80", "Total Triggers"]: row.append(0)
        else: row.append("")
    
    ws.append_row(row)
    print("Successfully added London Stock Exchange to Sources.")
except Exception as e:
    print("Error:", e)
