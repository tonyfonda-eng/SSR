import src.sheets as sheets

SHEET_URL = "https://docs.google.com/spreadsheets/d/1YDOyc8WReBei-7LKPLiXZtmOGCmoY7zuyTvyfMHeL4E/edit#gid=0"

try:
    gc = sheets.get_client()
    sh = gc.open_by_url(SHEET_URL)
    ws = sh.worksheet("Sources")
    
    records = ws.get_all_records()
    
    # Find the legacy Investegate row and delete it
    row_to_delete = None
    for i, r in enumerate(records):
        if r.get('Source') == 'Investegate LSE RNS (UK Announcements)':
            row_to_delete = i + 2 # +2 because 1-indexed and header row
            break
            
    if row_to_delete:
        ws.delete_rows(row_to_delete)
        print(f"Deleted legacy Investegate row at index {row_to_delete}")
    else:
        print("Legacy row not found.")
        
except Exception as e:
    print("Error:", e)
