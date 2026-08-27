import gspread
from src.sheets import get_spreadsheet
from src.config.settings import SHEET_URL

spreadsheet = get_spreadsheet(SHEET_URL)
worksheet = spreadsheet.worksheet("Pipeline")
records = worksheet.get_all_values()

# Find the columns
headers = records[0]
order_col = None
stage_id_col = None
active_col = None
desc_col = None

for i, h in enumerate(headers):
    h_lower = h.lower()
    if h_lower == "order": order_col = i
    elif h_lower == "stage_id": stage_id_col = i
    elif h_lower == "active": active_col = i
    elif h_lower == "description": desc_col = i

if None in (order_col, stage_id_col, active_col):
    print("Could not find required columns.")
    exit(1)

# We want to replace python_ticker_lookup with public_ticker_gate, or shift everything.
# Let's shift everything from 10 onwards by +1, and insert public_ticker_gate at 10.
cells_to_update = []
python_issuer_row_idx = -1

for r_idx, row in enumerate(records[1:], start=2):
    if len(row) > order_col and row[order_col].strip().isdigit():
        order_val = int(row[order_col].strip())
        if order_val >= 10:
            cells_to_update.append(gspread.Cell(row=r_idx, col=order_col+1, value=str(order_val+1)))
    
    if len(row) > stage_id_col and row[stage_id_col] == "python_issuer_extraction":
        python_issuer_row_idx = r_idx

if cells_to_update:
    worksheet.update_cells(cells_to_update)

# Now append a new row for public_ticker_gate
new_row = [""] * len(headers)
new_row[order_col] = "10"
new_row[stage_id_col] = "public_ticker_gate"
new_row[active_col] = "TRUE"
if desc_col is not None:
    new_row[desc_col] = "PUBLIC_TICKER_REQUIRED deterministic gate"

worksheet.append_row(new_row)
print("Added public_ticker_gate to Pipeline sheet at order 10 and shifted the rest.")
