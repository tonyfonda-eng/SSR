import sys
from pathlib import Path
import time

# Add the project root to sys.path so we can import src modules
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.sheets import get_client

SHEET_URL = "https://docs.google.com/spreadsheets/d/1YDOyc8WReBei-7LKPLiXZtmOGCmoY7zuyTvyfMHeL4E/edit#gid=0"

def append_rows(ws, rows):
    if not rows: return
    try:
        ws.append_rows(rows)
        print(f"    - Added {len(rows)} rows to '{ws.title}'.")
        time.sleep(1)
    except Exception as e:
        print(f"    - Failed to add rows to '{ws.title}': {e}")

def main():
    print(f"Connecting to Google Sheets...")
    client = get_client()
    try:
        sheet = client.open_by_url(SHEET_URL)
        print(f"Successfully opened workbook: {sheet.title}")
    except Exception as e:
        print(f"Failed to open workbook. Error: {e}")
        return

    # Prepopulate README
    readme = sheet.worksheet("README")
    readme_rows = [
        ["🟢 Light green", "User editable", "", "For the sheets you control"],
        ["⚪ White", "User input cells", "", "For specific cells you enter data into"],
        ["🟡 Light yellow", "AI recommendations awaiting review", "", "E.g., AI Research Queue"],
        ["🔵 Light blue", "Calculated summaries", "", ""],
        ["⚫ Grey", "Bot owned — never edit", "", "For all operational tabs"],
        ["🔴 Red", "Errors", "", ""],
        ["🟣 Purple", "Archived", "", "Historical data"],
        [],
        ["PIPELINE WORKFLOW:"],
        ["Sources -> Articles -> Cash Events -> Classification -> Playbook -> Research -> Review -> Alerts"]
    ]
    append_rows(readme, readme_rows)

    # Prepopulate Sources
    sources = sheet.worksheet("Sources")
    source_names = [
        "PR Newswire", "GlobeNewswire", "Business Wire", "SEC Edgar", 
        "LSE RNS", "TSX News", "Nasdaq", "HKEX", "ASX", "SEDAR+", 
        "Companies House", "FCA", "Competition authorities", "Bankruptcy courts"
    ]
    sources_rows = []
    for s in source_names:
        sources_rows.append(["TRUE", "High", s, "RSS/HTML", "", "", "15m", "Yes", "Active", ""])
    append_rows(sources, sources_rows)

    # Prepopulate Rules
    rules = sheet.worksheet("Rules")
    rules_rows = [
        ["Merger", "merger agreement, definitive agreement", "rumor, speculation", "all cash +10, board approved +5", "Classify as Cash Merger", "Cash Merger"],
        ["Tender Offer", "tender offer, commences offer", "rumor", "all cash +10", "Classify as Tender Offer", "Tender Offer"],
        ["Going Private", "going private, take private", "", "special committee +5", "Classify as Take Private", "Take Private"],
        ["Asset Sale", "sells assets, disposes of", "", "", "Classify as Asset Sale", "Asset Sale"],
        ["Rights Issue", "rights issue, rights offering", "", "", "Classify as Rights Issue", "Rights Issue"],
        ["Special Dividend", "special dividend, one-time dividend", "", "", "Classify as Special Dividend", "Special Dividend"],
        ["Liquidation", "liquidation, winding up", "", "", "Classify as Liquidation", "Liquidation"],
        ["Spin-off", "spin-off, separation", "", "", "Classify as Spin-off", "Spin-off"]
    ]
    append_rows(rules, rules_rows)

    # Prepopulate Playbooks
    playbooks = sheet.worksheet("Playbooks")
    playbooks_rows = [
        ["Cash Merger", "1. Cash?\n2. Financing secured?\n3. HSR?\n4. Break fee?\n5. Competing bidder?\n6. Management support?\n7. Regulatory risk?"],
        ["Tender offer", "1. Expiration date?\n2. Minimum tender condition?"],
        ["Spin-off", ""],
        ["Liquidation", ""],
        ["Distressed recapitalisation", ""]
    ]
    append_rows(playbooks, playbooks_rows)

    print("Prepopulation complete!")

if __name__ == "__main__":
    main()
