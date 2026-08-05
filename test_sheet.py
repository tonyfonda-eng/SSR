import sys
from src.config.settings import SHEET_URL
from src.sheets import get_client

try:
    client = get_client()
    sheet = client.open_by_url(SHEET_URL)
    print("Success! Title:", sheet.title)
    print("Worksheets:", [ws.title for ws in sheet.worksheets()])
except Exception as e:
    print("Error:", str(e))
