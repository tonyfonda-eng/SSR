import gspread
from google.oauth2.service_account import Credentials
import os
import json

def update_buyback_rule():
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
    
    rules_sheet = sheet.worksheet("Rules")
    records = rules_sheet.get_all_records()
    
    new_keywords = "buyback, share buyback, stock buyback, repurchase program, share repurchase, stock repurchase, buying back, repurchasing shares"
    
    for i, r in enumerate(records):
        name = r.get("Event Family", "")
        if name == "Buyback":
            row = i + 2 # +2 for 1-index and header
            rules_sheet.update(f"B{row}", [[new_keywords]])
            print(f"Successfully updated Buyback keywords on row {row}")
            return
            
    print("Buyback event family not found in Rules sheet.")

if __name__ == "__main__":
    update_buyback_rule()
