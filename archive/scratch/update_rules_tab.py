import src.sheets as sheets
import gspread

SHEET_URL = "https://docs.google.com/spreadsheets/d/1YDOyc8WReBei-7LKPLiXZtmOGCmoY7zuyTvyfMHeL4E/edit#gid=0"
gc = sheets.get_client()
sh = gc.open_by_url(SHEET_URL)

try:
    ws = sh.worksheet("Rules")
    headers = ws.row_values(1)
    if "Event Status" not in headers:
        col_index = len(headers) + 1
        ws.update_cell(1, col_index, "Event Status")
        ws.format(f"{gspread.utils.rowcol_to_a1(1, col_index)}", {"textFormat": {"bold": True}})
        print("Added 'Event Status' column to Rules.")
    else:
        print("'Event Status' column already exists.")
except Exception as e:
    print(f"Error: {e}")
