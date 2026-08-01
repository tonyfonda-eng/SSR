import src.sheets as sheets
import pprint

SHEET_URL = "https://docs.google.com/spreadsheets/d/1YDOyc8WReBei-7LKPLiXZtmOGCmoY7zuyTvyfMHeL4E/edit#gid=0"

try:
    gc = sheets.get_client()
    sh = gc.open_by_url(SHEET_URL)
    ws = sh.worksheet("Sources")
    
    records = ws.get_all_records()
    print(f"Total rows: {len(records)}")
    
    found_lse = False
    for i, r in enumerate(records):
        if "London Stock Exchange" in str(r.values()) or "investegate" in str(r.values()).lower():
            print(f"Row {i+2}:")
            pprint.pprint(r)
            found_lse = True
            
    if not found_lse:
        print("London Stock Exchange is completely missing! Re-adding...")
        headers = ws.row_values(1)
        row = []
        for header in headers:
            if header == "Enabled": row.append("TRUE")
            elif header == "Priority": row.append("Medium")
            elif header == "Source": row.append("London Stock Exchange")
            elif header == "Type": row.append("HTML")
            elif header == "HTML URL": row.append("https://www.investegate.co.uk")
            elif header == "Status": row.append("Active")
            elif header == "Ingestion Method": row.append("HTML")
            elif header in ["Parsed (Last Run)", "Cumulative Parsed (Today)"]: row.append(0)
            else: row.append("")
        ws.append_row(row)
        print("Restored London Stock Exchange!")
except Exception as e:
    print("Error:", e)
