import gspread
from google.oauth2.service_account import Credentials

from src.config.secrets import get_google_service_account

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly"
]


def load_rules(sheet_url):
    credentials = Credentials.from_service_account_info(
        get_google_service_account(),
        scopes=SCOPES,
    )

    client = gspread.authorize(credentials)

    sheet = client.open_by_url(sheet_url)

    worksheet = sheet.worksheet("Rules")

    return worksheet.get_all_records()
