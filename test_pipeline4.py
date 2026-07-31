from src.rules_engine import evaluate
from src.sheets import load_rules
SHEET_URL = "https://docs.google.com/spreadsheets/d/1YDOyc8WReBei-7LKPLiXZtmOGCmoY7zuyTvyfMHeL4E/edit#gid=0"
rules = load_rules(SHEET_URL)
title = "Plastec Technologies Announces Board Approval of Final Cash Dividend, Deregistration and Plan for Liquidation and Dissolution"

matches = evaluate(title, rules, threshold=0)
total_score = 0
for m in matches:
    if m.get('_Score') > 0:
        print(f"Rule: {m.get('Event Family')}, Score: {m.get('_Score')}, Evidence: {m.get('_Evidence')}")
        total_score = max(total_score, m.get('_Score'))

if total_score >= 10:
    print(f"\nCONCLUSION: YES, it passes the threshold of 10 with a highest score of {total_score}.")
else:
    print(f"\nCONCLUSION: NO, it fails the threshold of 10 with a highest score of {total_score}.")
