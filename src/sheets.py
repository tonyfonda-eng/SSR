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


def load_global_exclusions(sheet_url):
    client = get_client()
    sheet = client.open_by_url(sheet_url)
    try:
        worksheet = sheet.worksheet("Global Exclusions")
        # Grab all values in column A (index 1)
        values = worksheet.col_values(1)
        # Skip empty strings and a potential "Keyword" header
        return [v.strip().lower() for v in values if v.strip() and v.strip().lower() != "keyword"]
    except gspread.exceptions.WorksheetNotFound:
        print("[WARNING] 'Global Exclusions' tab not found in spreadsheet. Returning empty list.")
        return []

def load_gold_standards(sheet_url):
    client = get_client()
    sheet = client.open_by_url(sheet_url)
    try:
        worksheet = sheet.worksheet("AI Gold Standards")
        records = worksheet.get_all_records()
        # Map Event Family -> Gold Standard Example
        return {r.get('Event Family', '').strip(): r.get('Gold Standard Example', '').strip() for r in records if r.get('Event Family')}
    except gspread.exceptions.WorksheetNotFound:
        print("[WARNING] 'AI Gold Standards' tab not found. Returning empty dict.")
        return {}


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

def log_unknown_event(sheet_url, source, article_title, article_url, rules_score, ai_response):
    """
    Logs an unclassified event to the 'Unknown Events' tab.
    Architecture Principle #6: Unknown events are never ignored.
    Headers: Timestamp, Source, Article Title, URL, Rules Score, AI Response
    """
    client = get_client()
    sheet = client.open_by_url(sheet_url)
    try:
        worksheet = sheet.worksheet("Unknown Events")
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row_data = [timestamp, source, article_title, article_url, str(rules_score), ai_response]
        worksheet.append_row(row_data)
        print(f"[SHEETS] Logged unknown event to 'Unknown Events' tab for review.")
        return True
    except gspread.exceptions.WorksheetNotFound:
        print(f"[WARNING] 'Unknown Events' tab not found in the workbook. Please create it with headers: Timestamp | Source | Article Title | URL | Rules Score | AI Response")
        return False


def update_last_checked(sheet_url, source_stats, timestamp_str):
    """
    Batch updates the timestamp, parsed counts, and ingestion method for the given source names.
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
        
    if "Ingestion Method" not in header:
        header.append("Ingestion Method")
        col_idx_method = len(header) - 1
        updates.append({'range': gspread.utils.rowcol_to_a1(1, col_idx_method + 1), 'values': [["Ingestion Method"]]})
    else:
        col_idx_method = header.index("Ingestion Method")
        
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
            stat_data = source_stats[source_name]
            
            # Handle both old format (int) and new format (dict) just in case
            if isinstance(stat_data, dict):
                parsed_count = stat_data.get("count", 0)
                new_count = stat_data.get("new", 0)
                method_used = stat_data.get("method", "Unknown")
            else:
                parsed_count = stat_data
                new_count = 0
                method_used = "Unknown"
            
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
            cell_method = gspread.utils.rowcol_to_a1(row_idx + 1, col_idx_method + 1)
            cell_parsed_last = gspread.utils.rowcol_to_a1(row_idx + 1, col_idx_parsed_last + 1)
            cell_cumulative = gspread.utils.rowcol_to_a1(row_idx + 1, col_idx_cumulative + 1)
            
            updates.append({'range': cell_last_checked, 'values': [[timestamp_str]]})
            updates.append({'range': cell_method, 'values': [[method_used]]})
            updates.append({'range': cell_parsed_last, 'values': [[parsed_count]]})
            updates.append({'range': cell_cumulative, 'values': [[cumulative_val]]})
                
    if updates:
        worksheet.batch_update(updates)
        print(f"[SHEETS] Updated stats for {len(source_stats)} sources.")


def update_pipeline_metrics(sheet_url, funnel_metrics, timestamp_str):
    """
    Updates the funnel metrics on the 'Decision Pipeline' tab.
    Columns added dynamically: Count (Last Run), Timestamp (UTC), Cumulative Count (Today)
    """
    client = get_client()
    sheet = client.open_by_url(sheet_url)
    
    try:
        worksheet = sheet.worksheet("Decision Pipeline")
    except gspread.exceptions.WorksheetNotFound:
        print("[WARNING] 'Decision Pipeline' tab not found for metrics update.")
        return
        
    all_values = worksheet.get_all_values()
    if not all_values:
        return
        
    header = all_values[0]
    updates = []
    
    # 1. Ensure columns exist and get indices
    if "Count (Last Run)" not in header:
        header.append("Count (Last Run)")
        col_idx_count = len(header) - 1
        updates.append({'range': gspread.utils.rowcol_to_a1(1, col_idx_count + 1), 'values': [["Count (Last Run)"]]})
    else:
        col_idx_count = header.index("Count (Last Run)")
        
    if "Timestamp (UTC)" not in header:
        header.append("Timestamp (UTC)")
        col_idx_timestamp = len(header) - 1
        updates.append({'range': gspread.utils.rowcol_to_a1(1, col_idx_timestamp + 1), 'values': [["Timestamp (UTC)"]]})
    else:
        col_idx_timestamp = header.index("Timestamp (UTC)")
        
    if "Cumulative Count (Today)" not in header:
        header.append("Cumulative Count (Today)")
        col_idx_cumulative = len(header) - 1
        updates.append({'range': gspread.utils.rowcol_to_a1(1, col_idx_cumulative + 1), 'values': [["Cumulative Count (Today)"]]})
    else:
        col_idx_cumulative = header.index("Cumulative Count (Today)")
        
    today_date = timestamp_str.split()[0]
    
    # 2. Update data rows (assumes row 2 is Step 1, row 3 is Step 2, etc.)
    for row_idx, row in enumerate(all_values):
        if row_idx == 0:
            continue
            
        step_num_str = row[0] if len(row) > 0 else ""
        try:
            step_num = int(step_num_str)
        except ValueError:
            continue
            
        if step_num in funnel_metrics:
            new_count = funnel_metrics[step_num]
            
            current_timestamp = row[col_idx_timestamp] if len(row) > col_idx_timestamp else ""
            current_cumulative_str = row[col_idx_cumulative] if len(row) > col_idx_cumulative else "0"
            
            try:
                cumulative_val = int(current_cumulative_str)
            except ValueError:
                cumulative_val = 0
                
            if today_date in current_timestamp:
                cumulative_val += new_count
            else:
                cumulative_val = new_count
                
            cell_count = gspread.utils.rowcol_to_a1(row_idx + 1, col_idx_count + 1)
            cell_timestamp = gspread.utils.rowcol_to_a1(row_idx + 1, col_idx_timestamp + 1)
            cell_cumulative = gspread.utils.rowcol_to_a1(row_idx + 1, col_idx_cumulative + 1)
            
            updates.append({'range': cell_count, 'values': [[new_count]]})
            updates.append({'range': cell_timestamp, 'values': [[timestamp_str]]})
            updates.append({'range': cell_cumulative, 'values': [[cumulative_val]]})
            
    if updates:
        worksheet.batch_update(updates)
        print(f"[SHEETS] Updated decision pipeline funnel metrics.")


# ---------------------------------------------------------------------------
# Daily Memory (Google Sheets Backend)
# ---------------------------------------------------------------------------

def load_daily_memory(sheet_url):
    """
    Loads all issuers from the 'Daily Memory' tab to populate the in-memory cache.
    Returns a list of issuing companies.
    """
    client = get_client()
    sheet = client.open_by_url(sheet_url)
    try:
        worksheet = sheet.worksheet("Daily Memory")
        records = worksheet.get_all_records()
        return [str(r.get('Issuing Company', '')).lower() for r in records if r.get('Issuing Company')]
    except gspread.exceptions.WorksheetNotFound:
        print("[WARNING] 'Daily Memory' tab not found in Google Sheets. Returning empty memory.")
        return []
    except Exception as e:
        print(f"[ERROR] Failed to load Daily Memory from Sheets: {e}")

def log_normalization_review(sheet_url, source, language, document_type, title, url):
    """
    Logs an un-normalized foreign article to the Normalization Review tab.
    """
    try:
        sh = get_client().open_by_url(sheet_url)
        ws = sh.worksheet("Normalization Review")
        
        # [Date, Source, Language, Document Type, Title, URL]
        import datetime
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        row = [now_str, source, language, document_type, title, url]
        ws.append_row(row)
        print(f"[NORMALIZATION] Logged un-normalized article to Review tab: {title}")
    except Exception as e:
        print(f"[ERROR] Failed to log normalization review: {e}")
        return []

def batch_append_daily_memory(sheet_url, new_issuers):
    """
    Appends a list of new issuers to the 'Daily Memory' tab in a single API call.
    new_issuers is a list of strings: ['STRYKER', ...]
    """
    if not new_issuers:
        return
        
    client = get_client()
    sheet = client.open_by_url(sheet_url)
    try:
        worksheet = sheet.worksheet("Daily Memory")
        
        rows_to_append = []
        now_str = datetime.datetime.utcnow().isoformat()
        
        for issuer in new_issuers:
            rows_to_append.append([
                now_str,
                issuer
            ])
            
        worksheet.append_rows(rows_to_append, value_input_option='RAW')
        print(f"[SHEETS] Successfully appended {len(rows_to_append)} issuers to Daily Memory.")
        
    except gspread.exceptions.WorksheetNotFound:
        print("[WARNING] 'Daily Memory' tab not found. Could not save memory.")
    except Exception as e:
        print(f"[ERROR] Failed to batch append to Daily Memory: {e}")

def prune_daily_memory(sheet_url, max_age_hours=48):
    """
    Deletes rows from the 'Daily Memory' tab that are older than max_age_hours.
    This keeps the Google Sheet lightweight and prevents 500,000 row limits.
    """
    client = get_client()
    sheet = client.open_by_url(sheet_url)
    try:
        worksheet = sheet.worksheet("Daily Memory")
        records = worksheet.get_all_records()
        
        if not records:
            return
            
        now = datetime.datetime.utcnow()
        cutoff_date = now - datetime.timedelta(hours=max_age_hours)
        
        rows_to_delete = []
        # records is a list of dicts. Row 2 in sheet corresponds to records[0].
        # We iterate backwards so deleting a row doesn't shift the indices of subsequent rows we want to delete.
        for i in range(len(records) - 1, -1, -1):
            timestamp_str = records[i].get('Timestamp', '')
            if not timestamp_str:
                rows_to_delete.append(i + 2) # +2 because row 1 is header, and 0-indexed records
                continue
                
            try:
                # Handle isoformat with or without microseconds
                clean_ts = timestamp_str.split('.')[0] 
                row_date = datetime.datetime.strptime(clean_ts, "%Y-%m-%dT%H:%M:%S")
                if row_date < cutoff_date:
                    rows_to_delete.append(i + 2)
            except Exception:
                # If timestamp is mangled, delete it
                rows_to_delete.append(i + 2)
                
        # Batch delete rows (must delete from bottom up, which they already are due to reverse iteration)
        # Google Sheets API is tricky with batch deletes, so we do it one by one from bottom up,
        # or we can clear the whole sheet and rewrite the valid ones (much faster/safer).
        
        if len(rows_to_delete) > 100:
            # If there are many to delete, rewriting is safer and uses fewer API calls
            print(f"[SHEETS] Pruning {len(rows_to_delete)} old rows from Daily Memory by rewriting sheet...")
            valid_rows = [list(records[0].keys())] # Header
            
            for i, record in enumerate(records):
                if (i + 2) not in rows_to_delete:
                    valid_rows.append(list(record.values()))
                    
            worksheet.clear()
            worksheet.append_rows(valid_rows, value_input_option='RAW')
            print(f"[SHEETS] Daily Memory pruned successfully. Kept {len(valid_rows)-1} recent articles.")
            
    except gspread.exceptions.WorksheetNotFound:
        pass
    except Exception as e:
        print(f"[ERROR] Failed to prune Daily Memory: {e}")
