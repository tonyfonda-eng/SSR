import gspread
from google.oauth2.service_account import Credentials
import os
import json

def setup_kedm_playbook():
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
        playbooks_sheet = sheet.worksheet("Playbooks")
        
        records = playbooks_sheet.get_all_records()
        exists = False
        for r in records:
            if r.get("Playbook") == "KEDM Monitor":
                exists = True
                break
                
        instructions = """1. Extract the key special situations, M&A, and activist opportunities mentioned in this weekly monitor.
2. For each opportunity, list the Target, Acquirer (if any), and a 2-sentence summary of the investment thesis or catalyst.
3. If no actionable opportunities are mentioned, state 'No Actionable Opportunities'.
4. Do NOT hallucinate. Only extract from the text provided."""

        if not exists:
            playbooks_sheet.append_row(["KEDM Monitor", instructions])
            print("Appended 'KEDM Monitor' to Playbooks.")
        else:
            print("'KEDM Monitor' already exists in Playbooks.")
            
    except Exception as e:
        print(f"Failed to update playbooks: {e}")

if __name__ == "__main__":
    setup_kedm_playbook()
