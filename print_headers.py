from src.sheets import get_client, load_sources
SHEET_URL = "https://docs.google.com/spreadsheets/d/1YDOyc8WReBei-7LKPLiXZtmOGCmoY7zuyTvyfMHeL4E/edit#gid=0"
client = get_client()
sheet = client.open_by_url(SHEET_URL)
worksheet = sheet.worksheet("Sources")
print("Headers:", worksheet.get_all_values()[0])
