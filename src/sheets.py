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

def update_last_checked(sheet_url, source_stats, timestamp_str):
    """
    Batch updates the timestamp and parsed counts for the given source names.
    Creates necessary columns if they don't exist.
    """
    if not source_stats:
        return
        
    client = get_client()
    sheet = client.open_by_url(sheet_url)
    worksheet = sheet.worksheet("Sources")
    
    all_values = worksheet.get_all_values()
    if not all_values:
        return
        
    header = all_values[0]
    updates = []
    
    # 1. Ensure columns exist and get their indices
    if "Last Checked (UTC)" not in header:
        header.append("Last Checked (UTC)")
        col_idx_last_checked = len(header) - 1
        updates.append({'range': gspread.utils.rowcol_to_a1(1, col_idx_last_checked + 1), 'values': [["Last Checked (UTC)"]]})
    else:
        col_idx_last_checked = header.index("Last Checked (UTC)")
        
    if "Parsed (Last Run)" not in header:
        header.append("Parsed (Last Run)")
        col_idx_parsed_last = len(header) - 1
        updates.append({'range': gspread.utils.rowcol_to_a1(1, col_idx_parsed_last + 1), 'values': [["Parsed (Last Run)"]]})
    else:
        col_idx_parsed_last = header.index("Parsed (Last Run)")
        
    if "Cumulative Parsed (Today)" not in header:
        header.append("Cumulative Parsed (Today)")
        col_idx_cumulative = len(header) - 1
        updates.append({'range': gspread.utils.rowcol_to_a1(1, col_idx_cumulative + 1), 'values': [["Cumulative Parsed (Today)"]]})
    else:
        col_idx_cumulative = header.index("Cumulative Parsed (Today)")
        
    today_date = timestamp_str.split()[0]
    
    # 2. Update data rows
    for row_idx, row in enumerate(all_values):
        if row_idx == 0:
            continue
            
        source_name = row[2] if len(row) > 2 else ""
        if source_name in source_stats:
            parsed_count = source_stats[source_name]
            
            current_last_checked = row[col_idx_last_checked] if len(row) > col_idx_last_checked else ""
            current_cumulative_str = row[col_idx_cumulative] if len(row) > col_idx_cumulative else "0"
            
            try:
                cumulative_val = int(current_cumulative_str)
            except ValueError:
                cumulative_val = 0
                
            # If the last check was today, add to cumulative, else reset
            if today_date in current_last_checked:
                cumulative_val += parsed_count
            else:
                cumulative_val = parsed_count
                
            cell_last_checked = gspread.utils.rowcol_to_a1(row_idx + 1, col_idx_last_checked + 1)
            cell_parsed_last = gspread.utils.rowcol_to_a1(row_idx + 1, col_idx_parsed_last + 1)
            cell_cumulative = gspread.utils.rowcol_to_a1(row_idx + 1, col_idx_cumulative + 1)
            
            updates.append({'range': cell_last_checked, 'values': [[timestamp_str]]})
            updates.append({'range': cell_parsed_last, 'values': [[parsed_count]]})
            updates.append({'range': cell_cumulative, 'values': [[cumulative_val]]})
                
    if updates:
        worksheet.batch_update(updates)
        print(f"[SHEETS] Updated stats for {len(source_stats)} sources.")
