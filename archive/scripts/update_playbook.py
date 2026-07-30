import gspread
from google.oauth2.service_account import Credentials
import os
import json

def update_playbook():
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
    
    # 1. Update the Playbook
    playbooks_sheet = sheet.worksheet("Playbooks")
    records = playbooks_sheet.get_all_records()
    
    new_instructions = """1. Is the buyback significant compared to the current market cap? (Calculate % if market cap is available).
2. Is the buyback publicly disclosed and definitive, or just a generic authorization?
3. How is the buyback funded? (e.g., cash on hand, asset sale, or borrowing/debt).
4. If funded by borrowing, what is the impact on the balance sheet and leverage?
5. What is the timeline/dates around the buybacks? (e.g., by when are they completing it?)
6. Are there any recent news or earnings context prompting this from a capital allocation point of view?"""
    
    updated = False
    for i, r in enumerate(records):
        if r.get("Playbook", "") == "Share Buyback Playbook" or r.get("Playbook", "") == "Buyback":
            row = i + 2 # +2 for 1-index and header
            playbooks_sheet.update(f"B{row}", [[new_instructions]])
            print(f"Successfully updated Playbook instructions on row {row}")
            updated = True
            break
            
    if not updated:
        # If it doesn't exist, let's just append it
        playbooks_sheet.append_row(["Buyback", new_instructions])
        print("Appended new Buyback playbook.")

if __name__ == "__main__":
    update_playbook()
