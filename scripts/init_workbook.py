import sys
from pathlib import Path
import time

# Add the project root to sys.path so we can import src modules
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import gspread
from src.sheets import get_client

# Target Google Sheet URL (from tests/test_sheets.py)
SHEET_URL = "https://docs.google.com/spreadsheets/d/1YDOyc8WReBei-7LKPLiXZtmOGCmoY7zuyTvyfMHeL4E/edit#gid=0"

# Define the tabs and their headers
TABS = {
    # 1. Control Centre (User owns)
    "README": ["Legend", "Colour", "Meaning", "Notes"],
    "Pipeline": ["Stage", "Description", "Bot Action"],
    "Sources": ["Enabled", "Priority", "Source", "Type", "HTML URL", "RSS URL", "Poll", "Dedupe", "Status", "Notes"],
    "Rules": ["Event Family", "Keywords", "Exclusions", "Confidence Modifiers", "AI Prompt", "Downstream Playbook"],
    "Playbooks": ["Playbook", "Questions/Research Steps"],
    "Watchlist": ["Ticker", "Exchange", "Sector", "Market Cap", "Country", "Priority", "Notes"],
    "AI Research Queue": ["Timestamp", "Article Title", "URL", "Cash Event", "Confidence", "Action (Approve/Reject/Hold)"],
    "Settings": ["Setting Name", "Value", "Description"],
    
    # 2. Operational (Bot-owned, Grey)
    "Source Health": ["Timestamp", "Source", "Status", "Last Error"],
    "Crawl Log": ["Timestamp", "Source", "Articles Found"],
    "Articles": ["Timestamp", "URL", "Title", "Source", "Event Signals Score"],
    "Cash Events": ["Timestamp", "URL", "Detected Event", "Confidence Score", "Evidence Log"],
    "Classification": ["Timestamp", "Article URL", "AI Classification", "Reasoning"],
    "Alert Queue": ["Timestamp", "Alert Title", "Status"],
    "Alerts Sent": ["Timestamp", "Alert Title", "Destination"],
    "Dashboard": ["Metric", "Value", "Notes"],
    "Learning": ["Timestamp", "Event URL", "AI Prediction", "Human Correction", "Notes"],
    "Metrics": ["Timestamp", "Runtime", "API Calls", "Cost Estimate"],
    "Errors": ["Timestamp", "Component", "Error Message", "Traceback"],
    
    # 3. Archive
    "Archived Articles": ["Date Archived", "Original URL", "Title"],
    "Archived Alerts": ["Date Archived", "Alert Title"],
    "Old Companies": ["Date Removed", "Ticker", "Reason"],
    "Historical Statistics": ["Month", "Total Events", "True Positives", "False Positives"]
}

def col_to_letter(col_idx):
    col_str = ""
    while col_idx > 0:
        col_idx, remainder = divmod(col_idx - 1, 26)
        col_str = chr(65 + remainder) + col_str
    return col_str

def main():
    print(f"Connecting to Google Sheets...")
    client = get_client()
    try:
        sheet = client.open_by_url(SHEET_URL)
        print(f"Successfully opened workbook: {sheet.title}")
    except Exception as e:
        print(f"Failed to open workbook. Check URL or permissions. Error: {e}")
        return

    existing_worksheets = {ws.title: ws for ws in sheet.worksheets()}
    
    # First create new ones
    for tab_name, headers in TABS.items():
        if tab_name in existing_worksheets:
            print(f"[*] Tab '{tab_name}' already exists. Skipping creation.")
            ws = existing_worksheets[tab_name]
        else:
            print(f"[+] Creating tab '{tab_name}'...")
            ws = sheet.add_worksheet(title=tab_name, rows=100, cols=max(len(headers), 10))
            # Sleep briefly to avoid API rate limits
            time.sleep(1)
            
        # Add or update headers
        if headers:
            print(f"    - Formatting headers for '{tab_name}'...")
            end_col = col_to_letter(len(headers))
            cell_range = f"A1:{end_col}1"
            
            try:
                ws.update(values=[headers], range_name=cell_range)
                ws.format(cell_range, {
                    "textFormat": {"bold": True}
                })
            except Exception as e:
                print(f"    - Failed to set headers for '{tab_name}': {e}")
                
        time.sleep(1)

    # Now delete old tabs that are not in our list
    # We must ensure there is at least one tab left, but since we just created all TABS, we are safe.
    for tab_name, ws in existing_worksheets.items():
        if tab_name not in TABS:
            print(f"[-] Deleting old/unused tab '{tab_name}'...")
            try:
                sheet.del_worksheet(ws)
                time.sleep(1)
            except Exception as e:
                print(f"    - Failed to delete '{tab_name}': {e}")

    print(f"\nDone! Workbook v1.0 architecture initialized at: {SHEET_URL}")

if __name__ == "__main__":
    main()
