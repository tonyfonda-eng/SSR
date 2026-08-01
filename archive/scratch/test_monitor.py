from src.sheets import get_client, load_sources
import src.config.settings as settings

SHEET_URL = "https://docs.google.com/spreadsheets/d/1YDOyc8WReBei-7LKPLiXZtmOGCmoY7zuyTvyfMHeL4E/edit#gid=0"
try:
    sources = load_sources(SHEET_URL)
    print("Sources loaded:")
    for s in sources:
        print(s)
except Exception as e:
    print("Error:", e)
