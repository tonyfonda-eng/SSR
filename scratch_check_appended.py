import gspread
from src.sheets import get_spreadsheet
from src.config.settings import SHEET_URL

spreadsheet = get_spreadsheet(SHEET_URL)
worksheet = spreadsheet.worksheet("Pipeline")
records = worksheet.get_all_values()

for r in records[-5:]:
    print(r)
