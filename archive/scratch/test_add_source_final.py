import src.sheets as sheets

SHEET_URL = "https://docs.google.com/spreadsheets/d/1YDOyc8WReBei-7LKPLiXZtmOGCmoY7zuyTvyfMHeL4E/edit#gid=0"

try:
    gc = sheets.get_client()
    sh = gc.open_by_url(SHEET_URL)
    ws = sh.worksheet("Sources")
    records = ws.get_all_records()
    exists = any(r.get("Source Name") == "London Stock Exchange" for r in records)
    if exists:
        print("London Stock Exchange is already in Sources.")
    else:
        headers = ws.row_values(1)
        row = []
        for header in headers:
            if header == "Source Name": row.append("London Stock Exchange")
            elif header == "Active Scraper": row.append("London Stock Exchange")
            elif header == "Type": row.append("HTML (Investegate)")
            elif header == "Status": row.append("Active")
            elif header in ["Articles Scanned (Total)", "Confidence Over 80", "Total Triggers"]: row.append(0)
            else: row.append("")
        
        ws.append_row(row)
        print("Successfully added London Stock Exchange to Sources.")
except Exception as e:
    print("Error:", e)
