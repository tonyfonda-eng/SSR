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
    
    # Ensure physical grid has enough columns before we append new headers
    if worksheet.col_count < len(header) + 4:
        try:
            worksheet.add_cols(4)
        except Exception:
            pass
            
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
    
    if worksheet.col_count < len(header) + 3:
        try:
            worksheet.add_cols(3)
        except Exception:
            pass
            
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

def load_document_type_scores(sheet_url):
    """
    Loads Document Type scores from the 'Document Types' tab.
    Returns a dictionary mapping document type to integer score.
    """
    client = get_client()
    sheet = client.open_by_url(sheet_url)
    scores = {}
    try:
        worksheet = sheet.worksheet("Document Types")
        records = worksheet.get_all_records()
        for r in records:
            dt = str(r.get('Document Type', '')).lower().strip()
            score = r.get('Confidence Score', 0)
            if dt:
                try:
                    scores[dt] = int(score)
                except ValueError:
                    pass
    except Exception as e:
        print(f"[WARNING] Failed to load Document Type scores: {e}")
    
    return scores

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
        return []

def load_semantic_concepts(sheet_url):
    """
    Loads semantic concepts from the 'Semantic Concepts' tab.
    Returns a list of dicts with keys: Concept_ID, Description, Score, Countries, Languages, Examples
    """
    client = get_client()
    sheet = client.open_by_url(sheet_url)
    try:
        worksheet = sheet.worksheet("Semantic Concepts")
        return worksheet.get_all_records()
    except gspread.exceptions.WorksheetNotFound:
        print("[WARNING] 'Semantic Concepts' tab not found. Returning empty list.")
        return []
    except Exception as e:
        print(f"[ERROR] Failed to load Semantic Concepts: {e}")
        return []


def load_event_statuses(sheet_url):
    """
    Loads event statuses from the 'Event Status' tab.
    Returns a list of dicts with keys: Status_ID, Score, Languages
    """
    client = get_client()
    sheet = client.open_by_url(sheet_url)
    try:
        worksheet = sheet.worksheet("Event Status")
        return worksheet.get_all_records()
    except gspread.exceptions.WorksheetNotFound:
        print("[WARNING] 'Event Status' tab not found. Returning empty list.")
        return []
    except Exception as e:
        print(f"[ERROR] Failed to load Event Statuses: {e}")
        return []


def load_source_reliability(sheet_url):
    """
    Loads source reliability scores from the 'Sources' tab.
    Reads the 'Reliability' column if it exists.
    Returns a dict mapping source name -> int score.
    """
    client = get_client()
    sheet = client.open_by_url(sheet_url)
    scores = {}
    try:
        worksheet = sheet.worksheet("Sources")
        records = worksheet.get_all_records()
        for r in records:
            source_name = str(r.get('Source', '')).strip()
            reliability = r.get('Reliability', '')
            if source_name and reliability != '':
                try:
                    scores[source_name] = int(reliability)
                except (ValueError, TypeError):
                    pass
    except Exception as e:
        print(f"[WARNING] Failed to load Source Reliability scores: {e}")
    
    return scores


def log_ontology_review(sheet_url, country, source, language, document_type, raw_terms, title, url, detected_concepts):
    """
    Logs an article to the 'Ontology Review' tab for continuous learning.
    Every foreign article is logged, not just those with zero concepts.
    """
    try:
        sh = get_client().open_by_url(sheet_url)
        ws = sh.worksheet("Ontology Review")
        
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        raw_terms_str = ", ".join(raw_terms) if raw_terms else "None"
        concepts_str = ", ".join(detected_concepts) if detected_concepts else "None"
        
        # [Date, Country, Source, Language, Document Type, Raw Terms, Article Title, URL, Detected Concepts, Suggested Concept, Status]
        row = [now_str, country or "", source, language or "", document_type or "",
               raw_terms_str, title, url, concepts_str, "", ""]
        ws.append_row(row)
        print(f"[ONTOLOGY REVIEW] Logged article to review: {title}")
    except Exception as e:
        print(f"[ERROR] Failed to log ontology review: {e}")

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
        elif rows_to_delete:
            # Delete one by one from the bottom up to avoid index shifting
            for row_idx in rows_to_delete:
                worksheet.delete_rows(row_idx)
            print(f"[SHEETS] Pruned {len(rows_to_delete)} old rows from Daily Memory.")
            
    except gspread.exceptions.WorksheetNotFound:
        pass
    except Exception as e:
        print(f"[ERROR] Failed to prune Daily Memory: {e}")

# ---------------------------------------------------------------------------
# Operational Monitoring (Google Sheets Backend)
# ---------------------------------------------------------------------------

def aggregate_and_sync_yesterday(sheet_url):
    from src.database import is_yesterday_synced, get_yesterdays_metrics, mark_yesterday_synced
    import gspread
    
    if is_yesterday_synced():
        print("[SHEETS] Yesterday's metrics are already synced. Skipping.")
        return
        
    metrics = get_yesterdays_metrics()
    if not metrics["daily_stats"] or metrics["daily_stats"][0] is None:
        print("[SHEETS] No metrics found for yesterday. Marking as synced.")
        mark_yesterday_synced()
        return
        
    print("[SHEETS] Aggregating and syncing yesterday's operational data...")
    client = get_client()
    sheet = client.open_by_url(sheet_url)
    
    # 1. Daily Statistics
    try:
        ws_daily = sheet.worksheet("Daily Statistics")
        daily = metrics["daily_stats"]
        count = daily[16]
        avg_score = daily[14] / count if count > 0 else 0
        avg_conf = daily[15] / count if count > 0 else 0
        avg_time = daily[18] / count if count > 0 else 0
        max_time = daily[17] if daily[17] else 0
        
        row = [metrics["date"]] + list(daily[:14]) + [
            f"{avg_score:.2f}", f"{avg_conf:.2f}", f"{avg_time:.1f}", f"{max_time:.1f}"
        ]
        ws_daily.append_row(row)
    except gspread.exceptions.WorksheetNotFound:
        print("[WARNING] 'Daily Statistics' tab not found.")
        
    # 2. AI Usage
    try:
        ws_ai = sheet.worksheet("AI Usage")
        ai_rows = []
        for ai in metrics["ai_usage"]:
            reqs = ai[2]
            avg_rt = ai[10] / reqs if reqs > 0 else 0
            ai_rows.append([metrics["date"], ai[0], ai[1], reqs, ai[3], ai[4], ai[5], ai[6], ai[7], ai[8], ai[9], f"{avg_rt:.2f}", f"{ai[11]:.2f}", ai[12], ai[13]])
        if ai_rows:
            ws_ai.append_rows(ai_rows)
    except gspread.exceptions.WorksheetNotFound:
        print("[WARNING] 'AI Usage' tab not found.")
        
    # 3. Source Statistics
    try:
        ws_src = sheet.worksheet("Source Statistics")
        src_rows = []
        for src in metrics["source_stats"]:
            dl = src[1]
            conv = src[6] / dl if dl > 0 else 0
            avg_rt = src[7] / src[8] if src[8] > 0 else 0
            src_rows.append([metrics["date"], src[0], dl, src[2], src[3], src[4], src[5], src[6], f"{conv:.2%}", f"{avg_rt:.1f}"])
        if src_rows:
            ws_src.append_rows(src_rows)
    except gspread.exceptions.WorksheetNotFound:
        print("[WARNING] 'Source Statistics' tab not found.")
        
    # 4. Workflow Health
    try:
        ws_health = sheet.worksheet("Workflow Health")
        wh = metrics["workflow_health"]
        runs = wh[0]
        avg_rt = wh[3] / runs if runs > 0 else 0
        ws_health.append_row([metrics["date"], runs, wh[1], wh[2], f"{avg_rt:.1f}", wh[4], wh[5]])
    except gspread.exceptions.WorksheetNotFound:
        print("[WARNING] 'Workflow Health' tab not found.")
        
    mark_yesterday_synced()
    print("[SHEETS] Yesterday's sync complete.")

def get_system_settings(sheet_url):
    client = get_client()
    sheet = client.open_by_url(sheet_url)
    try:
        ws = sheet.worksheet("System Settings")
    except gspread.exceptions.WorksheetNotFound:
        print("[SHEETS] 'System Settings' tab not found. Provisioning default settings...")
        ws = sheet.add_worksheet(title="System Settings", rows="20", cols="2")
        ws.update("A1:B6", [
            ["Setting", "Value"],
            ["Download Drift Threshold", 20],
            ["Alert Drift Threshold", 50],
            ["AI Success Threshold", 80],
            ["Maximum Runtime Seconds", 240],
            ["Dashboard Publish Interval", 60]
        ])
        ws.format("A1:B1", {"textFormat": {"bold": True}})
        
    records = ws.get_all_records()
    settings = {
        "Download Drift Threshold": 20,
        "Alert Drift Threshold": 50,
        "AI Success Threshold": 80,
        "Maximum Runtime Seconds": 240,
        "Dashboard Publish Interval": 60
    }
    for row in records:
        key = row.get("Setting")
        val = row.get("Value")
        if key in settings and val != "":
            try:
                settings[key] = int(val)
            except ValueError:
                pass
                
    return settings

