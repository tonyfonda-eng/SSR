from src.sheets import get_worksheet
try:
    ws = get_worksheet("Sources")
    records = ws.get_all_records()
    exists = any(r.get("Source Name") == "London Stock Exchange" for r in records)
    if exists:
        print("London Stock Exchange is already in Sources.")
    else:
        # Append row: Source Name, Enabled, Active Scraper, Status, etc. (Check columns first)
        headers = ws.row_values(1)
        print("Headers:", headers)
        row = []
        for header in headers:
            if header == "Source Name": row.append("London Stock Exchange")
            elif header == "Active Scraper": row.append("lse.py")
            elif header == "Type": row.append("HTML/RSS")
            elif header == "Status": row.append("Active")
            elif header == "Articles Scanned (Total)": row.append("0")
            elif header == "Confidence Over 80": row.append("0")
            elif header == "Total Triggers": row.append("0")
            else: row.append("")
        
        ws.append_row(row)
        print("Successfully added London Stock Exchange to Sources.")
except Exception as e:
    print("Error:", e)
