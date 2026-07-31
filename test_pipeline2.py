from src.rules_engine import evaluate
from src.sheets import load_rules, get_client
import src.config.settings as settings

SHEET_URL = "https://docs.google.com/spreadsheets/d/1YDOyc8WReBei-7LKPLiXZtmOGCmoY7zuyTvyfMHeL4E/edit#gid=0"
title = "Stratus Properties Inc. Announces Initial Liquidating Distribution of $5.00 Per Share to Stockholders and Intention to Voluntarily Delist From Nasdaq and Deregister With SEC"

print("1. Loading Rules...")
rules = load_rules(SHEET_URL)

print("2. Evaluating against Rules Engine...")
matches = evaluate(title, rules, threshold=10)
if not matches:
    print("No rules matched or threshold not met. The bot would NOT flag this.")
else:
    print(f"Match found! Score: {matches[0]['_TotalScore']}")
    print("Evidence:", matches[0]['_Evidence'])
