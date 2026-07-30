import gspread
from google.oauth2.service_account import Credentials
import os
import json

def setup_naked_call_strategy():
    creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not creds_json:
        print("Error: GOOGLE_SERVICE_ACCOUNT_JSON not set")
        return
        
    creds_dict = json.loads(creds_json)
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    client = gspread.authorize(credentials)
    
    sheet_url = "https://docs.google.com/spreadsheets/d/1YDOyc8WReBei-7LKPLiXZtmOGCmoY7zuyTvyfMHeL4E/edit#gid=0"
    sheet = client.open_by_url(sheet_url)
    
    # 1. Update Rules
    try:
        rules_sheet = sheet.worksheet("Rules")
        
        # Check if it already exists
        records = rules_sheet.get_all_records()
        exists = False
        for r in records:
            if r.get("Event Family") == "M&A Naked Call Strategy":
                exists = True
                break
                
        if not exists:
            # We want to append to the top of the rules so it matches first
            # But appending row is easier. Let's just append.
            rules_sheet.append_row([
                "M&A Naked Call Strategy", 
                "all-cash transaction, definitive agreement to acquire, all cash merger, cash consideration of $", 
                "cash and stock, cash and shares, stock consideration, exchange ratio, mix of cash",
                "90" # High confidence weight
            ])
            print("Appended 'M&A Naked Call Strategy' to Rules.")
        else:
            print("'M&A Naked Call Strategy' already exists in Rules.")
            
    except Exception as e:
        print(f"Failed to update rules: {e}")
        
    # 2. Update Playbooks
    try:
        playbooks_sheet = sheet.worksheet("Playbooks")
        
        records = playbooks_sheet.get_all_records()
        exists = False
        for r in records:
            if r.get("Playbook") == "M&A Naked Call Strategy":
                exists = True
                break
                
        instructions = """1. What is the exact all-cash offer price per share?
2. Is the target company publicly listed? (If not, explicitly state PRIVATE).
3. Are there any significant regulatory (e.g., antitrust) or financing conditions that could cause the deal to break?
4. What is the expected timeline for closing the transaction?
5. Has the target company publicly commented on the offer?"""

        if not exists:
            playbooks_sheet.append_row(["M&A Naked Call Strategy", instructions])
            print("Appended 'M&A Naked Call Strategy' to Playbooks.")
        else:
            print("'M&A Naked Call Strategy' already exists in Playbooks.")
            
    except Exception as e:
        print(f"Failed to update playbooks: {e}")

if __name__ == "__main__":
    setup_naked_call_strategy()
