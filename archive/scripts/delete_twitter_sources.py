import gspread
from google.oauth2.service_account import Credentials
import os
import json

def delete_twitter_sources():
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

    records = sources_sheet.get_all_records()
    
    # We must iterate in reverse to safely delete rows without messing up the indices
    rows_deleted = 0
    for i in range(len(records) - 1, -1, -1):
        record = records[i]
        source_name = str(record.get("Source", ""))
        rss_url = str(record.get("RSS URL", ""))
        
        if "twitter" in source_name.lower() or "rss.app" in rss_url.lower():
            # i is the index in the records list.
            # get_all_records() skips the header row, so records[0] is row 2 in the sheet.
            row_to_delete = i + 2
            sources_sheet.delete_rows(row_to_delete)
            print(f"Deleted row {row_to_delete}: {source_name} ({rss_url})")
            rows_deleted += 1
            
    print(f"Finished. Deleted {rows_deleted} Twitter/RSS.app sources.")

if __name__ == "__main__":
    delete_twitter_sources()
