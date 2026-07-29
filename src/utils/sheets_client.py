import gspread
import json
import os
from google.oauth2.service_account import Credentials
from src.knowledge.schemas.core import Event

class SheetsClient:
    def __init__(self):
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        # Looks for the credentials file in the root directory
        creds_path = os.path.join(os.path.dirname(__file__), '..', '..', 'credentials.json')
        
        try:
            credentials = Credentials.from_service_account_file(creds_path, scopes=scopes)
            self.client = gspread.authorize(credentials)
            # You will need to share your Google Sheet with the service account email and name it "SSR_Workbook"
            self.sheet = self.client.open("SSR_Workbook").worksheet("Research Queue")
        except Exception as e:
            print(f"[Sheets Client] Offline mode. (Requires credentials.json): {e}")
            self.client = None

    def push_to_research_queue(self, event: Event):
        if not self.client:
            print("[Sheets Client] Offline mode: Skipping Google Sheet push.")
            return
            
        # Map our canonical Event to the manual's Research Queue layout
        row_data = [
            event.event_id,
            "CC-001",
            event.facts.get("ticker", "UNKNOWN"),
            event.facts.get("event_type", "Merger"),
            event.timestamps.discovered_at.strftime("%Y-%m-%d %H:%M"),
            "System Extracted M&A Options Event", 
            "New",
            "System",
            json.dumps(event.ai_interpretation) # Drops premium & vol notes here
        ]
        
        self.sheet.append_row(row_data)
        print(f"[Sheets Client] Successfully appended {event.event_id} to the active tracker.")
