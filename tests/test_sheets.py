from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.sheets import load_rules

SHEET_URL = "https://docs.google.com/spreadsheets/d/1YDOyc8WReBei-7LKPLiXZtmOGCmoY7zuyTvyfMHeL4E/edit#gid=0"

rules = load_rules(SHEET_URL)

print("=" * 60)
print(f"Loaded {len(rules)} rules")
print("=" * 60)

for rule in rules:
    print(rule)
