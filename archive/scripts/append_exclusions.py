import gspread
from google.oauth2.service_account import Credentials
import os
import json

def append_exclusions():
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
    
    try:
        worksheet = sheet.worksheet("Global Exclusions")
    except gspread.exceptions.WorksheetNotFound:
        worksheet = sheet.add_worksheet(title="Global Exclusions", rows=100, cols=2)
        worksheet.append_row(["Keyword", "Reason"])
        
    new_exclusions = [
        ["special purpose acquisition company", "SPAC IPO Noise"],
        ["blank check company", "SPAC IPO Noise"],
        ["initial business combination", "SPAC IPO Noise"],
        ["acquisition corp.", "SPAC IPO Noise"]
    ]
    
    existing_values = worksheet.col_values(1)
    
    added_count = 0
    for exclusion in new_exclusions:
        if exclusion[0].lower() not in [v.lower() for v in existing_values]:
            worksheet.append_row(exclusion)
            print(f"Added exclusion: {exclusion[0]}")
            added_count += 1
        else:
            print(f"Already exists: {exclusion[0]}")
            
    print(f"Successfully added {added_count} new global exclusions for SPACs.")

if __name__ == "__main__":
    append_exclusions()
