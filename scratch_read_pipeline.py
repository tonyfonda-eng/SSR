import json
from src.sheets import get_spreadsheet, get_client
from src.config.settings import SHEET_URL

spreadsheet = get_spreadsheet(SHEET_URL)
try:
    worksheet = spreadsheet.worksheet("Pipeline")
except Exception:
    worksheet = spreadsheet.worksheet("Process")

records = worksheet.get_all_records()
print(json.dumps(records, indent=2))
