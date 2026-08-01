from src.sheets import get_client
SHEET_URL = "https://docs.google.com/spreadsheets/d/1YDOyc8WReBei-7LKPLiXZtmOGCmoY7zuyTvyfMHeL4E/edit#gid=0"
client = get_client()
sheet = client.open_by_url(SHEET_URL)
ws = sheet.worksheet("Rules")
print("Headers:", ws.row_values(1))
