from src.config.settings import SHEET_URL
from src.sheets import get_client
import gspread

client = get_client()
doc = client.open_by_url(SHEET_URL)
sheet = doc.worksheet("Sources")
print("Headers:", sheet.row_values(1))
print("Row 2:", sheet.row_values(2))
