from src.scrapers.businesswire import BusinessWireScraper
from src.rules_engine import evaluate
from src.sheets import load_rules, load_playbooks, get_client
import src.config.settings as settings
import json

SHEET_URL = "https://docs.google.com/spreadsheets/d/1YDOyc8WReBei-7LKPLiXZtmOGCmoY7zuyTvyfMHeL4E/edit#gid=0"
url = "https://www.businesswire.com/news/home/20260701956972/en/Stratus-Properties-Inc.-Announces-Initial-Liquidating-Distribution-of-%245.00-Per-Share-to-Stockholders-and-Intention-to-Voluntarily-Delist-From-Nasdaq-and-Deregister-With-SEC"

print("1. Fetching body...")
scraper = BusinessWireScraper()
body = scraper.get_article_body(url)
if not body:
    print("Failed to fetch body.")
    exit(1)

print(f"Body extracted ({len(body)} chars).")

print("2. Loading Rules...")
rules = load_rules(SHEET_URL)
playbook_map = load_playbooks(SHEET_URL)

print("3. Evaluating against Rules Engine...")
matches = evaluate(body, rules, threshold=10)
if not matches:
    print("No rules matched or threshold not met. The bot would NOT flag this.")
else:
    print(f"Match found! Score: {matches[0]['_TotalScore']}")
    print("Evidence:", matches[0]['_Evidence'])
    
    print("\n4. Running AI Pipeline (Classification & Playbook)...")
    from src.ai import classify_event, execute_playbook
    from src.prompts import build_classification_prompt, build_playbook_prompt
    
    # Classification
    prompt = build_classification_prompt(
        url=url, 
        title="Stratus Properties Inc. Announces Initial Liquidating Distribution", 
        body=body, 
        playbooks=playbook_map
    )
    classification = classify_event(prompt)
    print("\n[AI CLASSIFICATION]")
    print(classification)
    
    if classification['confidence'] >= 80 and classification['event_family'] != "IRRELEVANT":
        print("\n5. Executing Playbook...")
        pb_prompt = build_playbook_prompt(
            url=url,
            title="Stratus Properties Inc. Announces Initial Liquidating Distribution",
            body=body,
            playbook_instructions=playbook_map.get(classification['event_family'], "Extract all relevant terms."),
            event_family=classification['event_family'],
            gold_standard=""
        )
        memo = execute_playbook(pb_prompt)
        print("\n[AI MEMO]")
        print(memo)
        print("\nCONCLUSION: YES, the bot WOULD flag and email this.")
    else:
        print("\nCONCLUSION: NO, the AI Confidence is too low or it was marked IRRELEVANT.")
