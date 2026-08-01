import os
import json
import gspread
from google.oauth2.service_account import Credentials

def get_client():
    """Initializes and returns an authorized gspread client using environment variables or credentials file."""
    creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    
    if creds_json:
        creds_dict = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        return gspread.authorize(creds)
    else:
        return gspread.service_account(filename="credentials.json")

def load_rules(sheet_url):
    """Loads operational rules from the Google Sheet."""
    client = get_client()
    spreadsheet = client.open_by_url(sheet_url)
    worksheet = spreadsheet.worksheet("Rules")
    return worksheet.get_all_records()

def load_document_type_scores(sheet_url):
    """Loads document type scores from the Google Sheet."""
    client = get_client()
    spreadsheet = client.open_by_url(sheet_url)
    worksheet = spreadsheet.worksheet("DocumentScores")
    return worksheet.get_all_records()