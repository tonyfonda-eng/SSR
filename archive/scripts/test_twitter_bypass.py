import sys
sys.path.append('.')
from monitor import _process_article
from src.sheets import load_rules

# Use dummy rules
rules = []
playbook_map = {}
global_exclusions = []
gold_standards = {}

print("Testing Twitter bypass logic...")
res = _process_article(
    source_name="Twitter - DealintCB",
    article_id="test_tweet_123",
    title="Test Tweet about AAPL",
    url="https://x.com/test",
    published="2026-07-30",
    body="I think AAPL is going to acquire someone. Very cheap stock here. Massive buyback incoming.",
    rules=rules,
    playbook_map=playbook_map,
    global_exclusions=global_exclusions,
    gold_standards=gold_standards,
    triage_all=False
)

print(f"Result (1 means processed/archived): {res}")
