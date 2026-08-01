from src.sheets import load_rules
SHEET_URL = "https://docs.google.com/spreadsheets/d/1YDOyc8WReBei-7LKPLiXZtmOGCmoY7zuyTvyfMHeL4E/edit#gid=0"
rules = load_rules(SHEET_URL)
for r in rules:
    print(r.get('Event Family'), "-->", r.get('Keywords'))
