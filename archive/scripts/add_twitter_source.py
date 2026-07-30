import gspread
from google.oauth2.service_account import Credentials
import os
import json

def add_twitter_source():
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
        sources_sheet = sheet.worksheet("Sources")
    except gspread.exceptions.WorksheetNotFound:
        print("Error: Sources worksheet not found.")
        return

    # Check if it already exists
    records = sources_sheet.get_all_records()
    for r in records:
        if r.get("Source") == "Twitter - DealintCB":
            print("Source 'Twitter - DealintCB' already exists!")
            return

    # Append row
    # Expected columns based on previous code: Source, RSS URL, Enabled, Triage All (Email Rejections)
    # Plus columns for Last Checked (UTC), Articles Parsed Last Run, Articles Parsed Today
    
    new_row = [
        "Twitter - DealintCB",  # Source
        "https://rss.app/feeds/zOicdzhRRAQUeiQh.xml", # RSS URL
        "TRUE", # Enabled
        "FALSE" # Triage All (Email Rejections)
    ]
    
    sources_sheet.append_row(new_row)
    print("Successfully added 'Twitter - DealintCB' to the Sources tab.")

if __name__ == "__main__":
    add_twitter_source()
