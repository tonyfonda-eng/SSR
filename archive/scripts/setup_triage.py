import gspread
from google.oauth2.service_account import Credentials
import os
import json

def setup_triage():
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
    
    # 1. Sources Sheet Update
    try:
        sources_sheet = sheet.worksheet("Sources")
        headers = sources_sheet.row_values(1)
        
        # Add column if not exists
        triage_col_index = None
        if "Triage All (Email Rejections)" not in headers:
            # Let's add it at the end (e.g. column O)
            next_col = len(headers) + 1
            sources_sheet.update_cell(1, next_col, "Triage All (Email Rejections)")
            triage_col_index = next_col
            print("Added 'Triage All (Email Rejections)' header to Sources tab.")
        else:
            triage_col_index = headers.index("Triage All (Email Rejections)") + 1
            
        # Add the actual source
        records = sources_sheet.get_all_records()
        exists = False
        for r in records:
            if r.get("Source") == "Special Situations Digest":
                exists = True
                break
                
        if not exists:
            new_row = ["TRUE", "High", "Special Situations Digest", "RSS", "https://specialsitsdigest.com/situations-database/", "https://specialsitsdigest.com/feed/", "15", "TRUE", "Active", "Dynamic Triage Source", "", 0, 0, "RSS"]
            # Pad new_row to match the number of columns, then set the Triage column to TRUE
            while len(new_row) < triage_col_index:
                new_row.append("")
            new_row[triage_col_index - 1] = "TRUE"
            
            sources_sheet.append_row(new_row)
            print("Appended 'Special Situations Digest' to Sources with Triage All = TRUE.")
        else:
            print("'Special Situations Digest' already exists in Sources.")
            
    except Exception as e:
        print(f"Failed to update Sources: {e}")
        
    # 2. Add Rejection Playbook
    try:
        playbooks_sheet = sheet.worksheet("Playbooks")
        
        records = playbooks_sheet.get_all_records()
        exists = False
        for r in records:
            if r.get("Playbook") == "Triage Rejection":
                exists = True
                break
                
        instructions = """1. Explain explicitly WHY this opportunity does not meet our strict investment criteria (e.g., target is not public, deal is not 100% cash, missing definitive agreement, or it is a false positive).
2. What is the key missing piece of data that caused this rejection?
3. State 'No Further Action Required.'"""

        if not exists:
            playbooks_sheet.append_row(["Triage Rejection", instructions])
            print("Appended 'Triage Rejection' to Playbooks.")
        else:
            print("'Triage Rejection' already exists in Playbooks.")
            
    except Exception as e:
        print(f"Failed to update playbooks: {e}")

if __name__ == "__main__":
    setup_triage()
