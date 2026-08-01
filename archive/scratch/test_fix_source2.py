import src.sheets as sheets

SHEET_URL = "https://docs.google.com/spreadsheets/d/1YDOyc8WReBei-7LKPLiXZtmOGCmoY7zuyTvyfMHeL4E/edit#gid=0"

try:
    gc = sheets.get_client()
    sh = gc.open_by_url(SHEET_URL)
    ws = sh.worksheet("Sources")
    
    records = ws.get_all_records()
    
    # Find "London Stock Exchange"
    for i, r in enumerate(records):
        if r.get("Source") == "London Stock Exchange":
            row_idx = i + 2 # +2 because 1-indexed and header row
            
            # Find the column index for "HTML URL"
            headers = ws.row_values(1)
            col_idx = headers.index("HTML URL") + 1
            
            # Update the cell
            ws.update_cell(row_idx, col_idx, "https://www.investegate.co.uk")
            print(f"Updated HTML URL for London Stock Exchange on row {row_idx}, col {col_idx}")
            break
            
except Exception as e:
    print("Error:", e)
