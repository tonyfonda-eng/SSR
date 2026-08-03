import os
import json
import time
import datetime
import gspread
from google.oauth2.service_account import Credentials

_cached_client = None
_cached_spreadsheet = None

def get_client():
    global _cached_client
    if _cached_client is not None:
        return _cached_client
        
    creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    
    if creds_json:
        try:
            creds_dict = json.loads(creds_json)
            creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
            _cached_client = gspread.authorize(creds)
        except json.JSONDecodeError:
            print("[CRITICAL] GOOGLE_SERVICE_ACCOUNT_JSON is malformed. Falling back to local credentials.json")
            _cached_client = gspread.service_account(filename="credentials.json")
    else:
        _cached_client = gspread.service_account(filename="credentials.json")
        
    return _cached_client

def get_spreadsheet(sheet_url):
    global _cached_spreadsheet
    if _cached_spreadsheet is not None:
        return _cached_spreadsheet
        
    client = get_client()
    _cached_spreadsheet = client.open_by_url(sheet_url)
    return _cached_spreadsheet

def _safe_get_records(sheet_url, sheet_names, retries=3, backoff=2.0):
    spreadsheet = get_spreadsheet(sheet_url)
    for attempt in range(retries):
        for name in sheet_names:
            try:
                worksheet = spreadsheet.worksheet(name)
                return worksheet.get_all_records()
            except gspread.exceptions.WorksheetNotFound:
                continue 
            except Exception as e:
                if attempt == retries - 1:
                    print(f"[ERROR] Failed to fetch '{name}' after {retries} attempts: {e}")
                else:
                    time.sleep(backoff * (attempt + 1))
    return [] 

def load_rules(sheet_url):
    return _safe_get_records(sheet_url, ["Rules"])

def load_sources(sheet_url):
    return _safe_get_records(sheet_url, ["Sources"])

def load_playbooks(sheet_url):
    return _safe_get_records(sheet_url, ["Playbooks"])

def load_global_exclusions(sheet_url):
    return _safe_get_records(sheet_url, ["GlobalExclusions", "Global Exclusions"])

def load_gold_standards(sheet_url):
    return _safe_get_records(sheet_url, ["GoldStandards", "Gold Standards"])

def load_daily_memory(sheet_url, *args, **kwargs):
    spreadsheet = get_spreadsheet(sheet_url)
    worksheet = None
    
    for name in ["DailyMemory", "Daily Memory"]:
        try:
            worksheet = spreadsheet.worksheet(name)
            break
        except gspread.exceptions.WorksheetNotFound:
            continue
            
    if not worksheet:
        return []

    raw_rows = worksheet.get_all_values()
    if not raw_rows or len(raw_rows) <= 1:
        return []

    processed_records = []
    current_date_str = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    should_flush = False

    for row in raw_rows[1:]:
        if not row or len(row) < 1:
            continue
        
        issuer_name = row[0].strip()
        timestamp_raw = row[1].strip() if len(row) > 1 else ""

        if not issuer_name:
            continue

        if timestamp_raw and current_date_str not in timestamp_raw:
            should_flush = True
        
        processed_records.append({
            "issuer": issuer_name,
            "timestamp": timestamp_raw
        })

    if should_flush:
        print(f"[DAILY MEMORY] New calendar day detected ({current_date_str}). Auto-flushing stale weekend rows...")
        try:
            worksheet.clear()
            worksheet.append_row(["Issuer", "Timestamp"]) 
            return [] 
        except Exception as e:
            print(f"[ERROR] Failed to execute automated daily memory flush: {e}")

    print(f"[DAILY MEMORY] Cleanly loaded {len(processed_records)} active tracking issuers from Google Sheets.")
    return processed_records

def load_source_reliability(sheet_url, *args, **kwargs):
    return _safe_get_records(sheet_url, ["SourceReliability", "Source Reliability"])

def load_document_type_scores(sheet_url):
    return _safe_get_records(sheet_url, ["DocumentScores", "Document Scores", "Document Types"])

def get_system_settings(sheet_url):
    return _safe_get_records(sheet_url, ["Settings", "SystemSettings"])

def load_semantic_concepts(sheet_url):
    return _safe_get_records(sheet_url, ["Semantic Concepts", "SemanticConcepts"])

def load_event_statuses(sheet_url):
    return _safe_get_records(sheet_url, ["Event Status", "EventStatus"])

def append_to_research_queue(sheet_url, data_row):
    spreadsheet = get_spreadsheet(sheet_url)
    try:
        worksheet = spreadsheet.worksheet("ResearchQueue")
    except gspread.exceptions.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title="ResearchQueue", rows=1000, cols=10)
        worksheet.append_row(["Timestamp", "Ticker", "Issuer", "Event Family", "URL", "Status"])
    
    if isinstance(data_row, dict):
        row_values = [
            data_row.get("timestamp", ""),
            data_row.get("ticker", ""),
            data_row.get("issuer", ""),
            data_row.get("event_family", ""),
            data_row.get("url", ""),
            data_row.get("status", "Pending")
        ]
    else:
        row_values = data_row
    worksheet.append_row(row_values)

def batch_append_to_research_queue(sheet_url, data_rows):
    if not data_rows:
        return
        
    spreadsheet = get_spreadsheet(sheet_url)
    try:
        worksheet = spreadsheet.worksheet("ResearchQueue")
    except gspread.exceptions.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title="ResearchQueue", rows=1000, cols=10)
        worksheet.append_row(["Timestamp", "Ticker", "Issuer", "Event Family", "URL", "Status"])
    
    formatted_rows = []
    for row in data_rows:
        if isinstance(row, dict):
            formatted_rows.append([
                row.get("timestamp", ""),
                row.get("ticker", ""),
                row.get("issuer", ""),
                row.get("event_family", ""),
                row.get("url", ""),
                row.get("status", "Pending")
            ])
        else:
            formatted_rows.append(row)
            
    worksheet.append_rows(formatted_rows)

def log_unknown_event(sheet_url, *args, **kwargs):
    spreadsheet = get_spreadsheet(sheet_url)
    try:
        worksheet = spreadsheet.worksheet("UnknownEvents")
    except gspread.exceptions.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title="UnknownEvents", rows=1000, cols=5)
        worksheet.append_row(["Timestamp", "Title", "Source", "Raw Text"])
        
    row_values = [
        kwargs.get("timestamp", ""),
        kwargs.get("article_title", ""),
        kwargs.get("Source", ""),
        str(kwargs.get("ai_response", ""))
    ]
    worksheet.append_row(row_values)

def update_last_checked(sheet_url, source_name):
    if not source_name:
        return
    spreadsheet = get_spreadsheet(sheet_url)
    try:
        worksheet = spreadsheet.worksheet("Sources")
    except gspread.exceptions.WorksheetNotFound:
        return
    
    try:
        cell = worksheet.find(source_name)
        if cell:
            header_row = worksheet.row_values(1)
            col_index = None
            for idx, header in enumerate(header_row, 1):
                if "checked" in header.lower() or "timestamp" in header.lower():
                    col_index = idx
                    break
            
            if col_index:
                ts = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S GMT")
                worksheet.update_cell(cell.row, col_index, ts)
    except Exception as e:
        pass # Silently proceed so we don't break pipeline if gspread hangs

def update_pipeline_metrics(sheet_url, *args, **kwargs):
    pass 

def batch_append_daily_memory(sheet_url, new_issuers):
    if not new_issuers:
        return
    spreadsheet = get_spreadsheet(sheet_url)
    
    worksheet = None
    for name in ["Daily Memory", "DailyMemory"]:
        try:
            worksheet = spreadsheet.worksheet(name)
            break
        except gspread.exceptions.WorksheetNotFound:
            continue
            
    if not worksheet:
        worksheet = spreadsheet.add_worksheet(title="Daily Memory", rows=1000, cols=2)
        worksheet.append_row(["Issuer", "Timestamp"])
        
    ts = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S GMT")
    rows = [[issuer, ts] for issuer in new_issuers]
    worksheet.append_rows(rows)

def prune_daily_memory(sheet_url, *args, **kwargs):
    pass

def log_ontology_review(sheet_url, *args, **kwargs):
    pass

def aggregate_and_sync_yesterday(sheet_url, *args, **kwargs):
    pass