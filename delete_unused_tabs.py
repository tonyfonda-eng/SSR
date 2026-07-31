import gspread
from src.config.secrets import get_google_service_account
from google.oauth2.service_account import Credentials

SHEET_URL = "https://docs.google.com/spreadsheets/d/1YDOyc8WReBei-7LKPLiXZtmOGCmoY7zuyTvyfMHeL4E/edit#gid=0"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

TABS_TO_DELETE = [
    "Articles",
    "Crawl Log",
    "Source Health",
    "Alert Queue",
    "Alerts Sent",
    "Errors",
    "Archived Articles",
    "Archived Alerts",
    "Old Companies",
    "Classification",
    "Cash Events",
    "Pipeline"
]

def get_client():
    credentials = Credentials.from_service_account_info(
        get_google_service_account(),
        scopes=SCOPES,
    )
    return gspread.authorize(credentials)

def main():
    print("Connecting to Google Sheets...")
    client = get_client()
    sheet = client.open_by_url(SHEET_URL)
    
    deleted_count = 0
    for tab_name in TABS_TO_DELETE:
        try:
            worksheet = sheet.worksheet(tab_name)
            sheet.del_worksheet(worksheet)
            print(f"✅ Deleted: {tab_name}")
            deleted_count += 1
        except gspread.exceptions.WorksheetNotFound:
            print(f"⏭️  Skipped: {tab_name} (Already deleted or doesn't exist)")
            
    print(f"\nCleanup complete! Deleted {deleted_count} unused operational tabs.")

if __name__ == "__main__":
    main()
