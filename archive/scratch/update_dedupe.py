import src.sheets as sheets

SHEET_URL = "https://docs.google.com/spreadsheets/d/1YDOyc8WReBei-7LKPLiXZtmOGCmoY7zuyTvyfMHeL4E/edit#gid=0"

try:
    gc = sheets.get_client()
    sh = gc.open_by_url(SHEET_URL)
    ws = sh.worksheet("Sources")
    
    headers = ws.row_values(1)
    records = ws.get_all_records()
    col_idx_dedupe = headers.index("Dedupe") + 1
    
    for i, r in enumerate(records):
        if "Special Situations Digest" in str(r.get("Source", "")):
            row_idx = i + 2 # +2 because 1-indexed and header row
            cell = sheets.gspread.utils.rowcol_to_a1(row_idx, col_idx_dedupe)
            ws.update_acell(cell, "FALSE")
            print(f"Disabled deduplication for Special Situations Digest at row {row_idx}")
            break
            
except Exception as e:
    print("Error:", e)
