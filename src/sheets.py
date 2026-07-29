import gspread
from google.oauth2.service_account import Credentials
import datetime

from src.config.secrets import get_google_service_account

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets"
]

def get_client():
    credentials = Credentials.from_service_account_info(
        get_google_service_account(),
        scopes=SCOPES,
    )
    return gspread.authorize(credentials)


def load_rules(sheet_url):
    client = get_client()
    sheet = client.open_by_url(sheet_url)
    worksheet = sheet.worksheet("Rules")
    return worksheet.get_all_records()


def load_sources(sheet_url):
    client = get_client()
    sheet = client.open_by_url(sheet_url)
    worksheet = sheet.worksheet("Sources")
    return worksheet.get_all_records()


def load_playbooks(sheet_url):
    client = get_client()
    sheet = client.open_by_url(sheet_url)
    worksheet = sheet.worksheet("Playbooks")
    return worksheet.get_all_records()


def append_to_research_queue(sheet_url, article_title, article_url, event_family, confidence, action="Hold"):
    """
    Appends a row of data to the 'AI Research Queue' tab.
    Headers: Timestamp, Article Title, URL, Cash Event, Confidence, Action
    """
    client = get_client()
    sheet = client.open_by_url(sheet_url)
    try:
        worksheet = sheet.worksheet("AI Research Queue")
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row_data = [timestamp, article_title, article_url, event_family, str(confidence), action]
        worksheet.append_row(row_data)
        print(f"[SHEETS] Successfully appended {event_family} match to AI Research Queue.")
        return True
    except gspread.exceptions.WorksheetNotFound:
        print(f"[WARNING] 'AI Research Queue' tab not found in the workbook.")
        return False
