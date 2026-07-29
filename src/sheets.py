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

def update_last_checked(sheet_url, sources_to_update, timestamp_str):
    """
    Batch updates the 'Last Checked (UTC)' column (K / 11) for the given source names.
    Only updates sources if their current value doesn't already start with today's date.
    """
    if not sources_to_update:
        return
        
    client = get_client()
    sheet = client.open_by_url(sheet_url)
    worksheet = sheet.worksheet("Sources")
    
    all_values = worksheet.get_all_values()
    
    # Find column index for 'Last Checked (UTC)'. It should be 10 (0-indexed) if it's the 11th column.
    header = all_values[0]
    try:
        col_idx = header.index("Last Checked (UTC)")
    except ValueError:
        print("[WARNING] 'Last Checked (UTC)' column not found in Sources sheet.")
        return
        
    updates = []
    # today_str = timestamp_str.split()[0] # e.g. '2026-07-29'
    
    for row_idx, row in enumerate(all_values):
        if row_idx == 0:
            continue
            
        source_name = row[2] # 3rd column is 'Source'
        if source_name in sources_to_update:
            current_val = row[col_idx] if len(row) > col_idx else ""
            
            # If the current value doesn't match today's date string, we update it
            # We check if today's date is in the string to avoid updating multiple times a day
            today_date = timestamp_str.split()[0]
            if today_date not in current_val:
                # Add to batch update (row_idx is 0-indexed, google sheets is 1-indexed)
                cell_name = gspread.utils.rowcol_to_a1(row_idx + 1, col_idx + 1)
                updates.append({'range': cell_name, 'values': [[timestamp_str]]})
                
    if updates:
        worksheet.batch_update(updates)
        print(f"[SHEETS] Updated 'Last Checked' timestamp for {len(updates)} sources.")
