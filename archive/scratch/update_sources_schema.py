import src.sheets as sheets

SHEET_URL = "https://docs.google.com/spreadsheets/d/1YDOyc8WReBei-7LKPLiXZtmOGCmoY7zuyTvyfMHeL4E/edit#gid=0"

new_headers = [
    "Enabled", "Priority", "Source", "Country", "Language", "Regulator", 
    "Distributor", "Delay", "Coverage", "RSS?", "HTML?", "API?", 
    "Anti-bot score", "Type", "HTML URL", "Status", "Ingestion Method", 
    "Parsed (Last Run)", "Cumulative Parsed (Today)"
]

try:
    gc = sheets.get_client()
    sh = gc.open_by_url(SHEET_URL)
    ws = sh.worksheet("Sources")
    
    # Update row 1 with new headers
    cell_list = ws.range(f"A1:{sheets.gspread.utils.rowcol_to_a1(1, len(new_headers))}")
    for i, cell in enumerate(cell_list):
        cell.value = new_headers[i]
        
    ws.update_cells(cell_list)
    print("Schema updated successfully!")
    
except Exception as e:
    print(f"Error updating schema: {e}")
