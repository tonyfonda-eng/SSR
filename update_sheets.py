import src.sheets as sheets
import gspread

SHEET_URL = "https://docs.google.com/spreadsheets/d/1YDOyc8WReBei-7LKPLiXZtmOGCmoY7zuyTvyfMHeL4E/edit#gid=0"

gc = sheets.get_client()
sh = gc.open_by_url(SHEET_URL)

# 1. Create 'Document Types' tab
try:
    ws = sh.add_worksheet(title="Document Types", rows=100, cols=2)
    ws.append_row(["Document Type", "Confidence Score"])
    ws.format("A1:B1", {"textFormat": {"bold": True}})
    
    # Default scores
    scores = [
        ["Ad-hoc", 40],
        ["Inside Information", 40],
        ["Información Privilegiada", 40],
        ["Price Sensitive", 35],
        ["Regulated Information", 30],
        ["Regulatory", 30],
        ["Corporate News", 5],
        ["Press Release", 0]
    ]
    ws.append_rows(scores)
    print("Created 'Document Types' tab.")
except gspread.exceptions.APIError as e:
    print(f"Document Types tab might already exist: {e}")

# 2. Add 'Semantic Concepts' column to 'Rules'
try:
    ws_rules = sh.worksheet("Rules")
    headers = ws_rules.row_values(1)
    if "Semantic Concepts" not in headers:
        col_index = len(headers) + 1
        ws_rules.update_cell(1, col_index, "Semantic Concepts")
        ws_rules.format(f"{gspread.utils.rowcol_to_a1(1, col_index)}", {"textFormat": {"bold": True}})
        print("Added 'Semantic Concepts' column to Rules.")
    else:
        print("'Semantic Concepts' column already exists in Rules.")
except Exception as e:
    print(f"Error updating Rules tab: {e}")

# 3. Rename 'Normalization Review' to 'Ontology Review'
try:
    ws_review = sh.worksheet("Normalization Review")
    ws_review.update_title("Ontology Review")
    print("Renamed 'Normalization Review' to 'Ontology Review'.")
except gspread.exceptions.WorksheetNotFound:
    print("'Normalization Review' not found. It might have been renamed already.")
except Exception as e:
    print(f"Error renaming review tab: {e}")

