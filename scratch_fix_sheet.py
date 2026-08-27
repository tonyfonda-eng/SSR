import gspread
from src.sheets import get_spreadsheet
from src.config.settings import SHEET_URL

spreadsheet = get_spreadsheet(SHEET_URL)
worksheet = spreadsheet.worksheet("Pipeline")
records = worksheet.get_all_values()

# Find the mess row and delete it
mess_row_idx = None
for i, r in enumerate(records):
    if len(r) >= 8 and r[7] == 'public_ticker_gate':
        mess_row_idx = i + 1
        break

if mess_row_idx:
    worksheet.delete_rows(mess_row_idx)

# Find where to insert it: right after python_issuer_extraction
insert_idx = None
for i, r in enumerate(records):
    if len(r) > 1 and r[1] == 'python_issuer_extraction':
        insert_idx = i + 2 # +1 for 1-based index, +1 to insert AFTER it
        break

if insert_idx:
    # Insert row
    worksheet.insert_row(["10", "public_ticker_gate", "TRUE", "PUBLIC_TICKER_REQUIRED deterministic gate", "", "", "", "", "", ""], index=insert_idx)
    print(f"Inserted correctly at row {insert_idx}")
else:
    print("Could not find python_issuer_extraction")
