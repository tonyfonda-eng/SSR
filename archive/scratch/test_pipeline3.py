from src.rules_engine import evaluate
from src.sheets import load_rules
SHEET_URL = "https://docs.google.com/spreadsheets/d/1YDOyc8WReBei-7LKPLiXZtmOGCmoY7zuyTvyfMHeL4E/edit#gid=0"
rules = load_rules(SHEET_URL)
title = "Stratus Properties Inc. Announces Initial Liquidating Distribution of $5.00 Per Share to Stockholders and Intention to Voluntarily Delist From Nasdaq and Deregister With SEC"

matches = evaluate(title, rules, threshold=0)
for m in matches:
    print(f"Rule: {m.get('Event Family')}, Score: {m.get('_Score')}, Evidence: {m.get('_Evidence')}")
