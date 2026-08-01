import src.sheets as sheets

SHEET_URL = "https://docs.google.com/spreadsheets/d/1YDOyc8WReBei-7LKPLiXZtmOGCmoY7zuyTvyfMHeL4E/edit#gid=0"

try:
    gc = sheets.get_client()
    sh = gc.open_by_url(SHEET_URL)
    ws = sh.worksheet("Sources")
    
    records = ws.get_all_records()
    
    # Find the malformed row and delete it
    row_to_delete = None
    for i, r in enumerate(records):
        if r.get('Type') == 'HTML (Investegate)' and r.get('Source') == '':
            row_to_delete = i + 2 # +2 because 1-indexed and header row
            break
            
    if row_to_delete:
        ws.delete_rows(row_to_delete)
        print(f"Deleted malformed row {row_to_delete}")
        
    # Find if "London Stock Exchange" already exists
    records = ws.get_all_records()
    exists = any(r.get("Source") == "London Stock Exchange" for r in records)
    if not exists:
        headers = ws.row_values(1)
        row = []
        for header in headers:
            if header == "Enabled": row.append("TRUE")
            elif header == "Priority": row.append("High")
            elif header == "Source": row.append("London Stock Exchange")
            elif header == "Type": row.append("HTML")
            elif header == "Status": row.append("Active")
            elif header == "Ingestion Method": row.append("HTML")
            elif header in ["Parsed (Last Run)", "Cumulative Parsed (Today)"]: row.append(0)
            else: row.append("")
        
        ws.append_row(row)
        print("Successfully added London Stock Exchange with correct columns.")
    else:
        print("London Stock Exchange already correctly exists.")
        
except Exception as e:
    print("Error:", e)
