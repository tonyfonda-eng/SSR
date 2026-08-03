import os
import json
import time
import gspread
from google.oauth2.service_account import Credentials

# --- GLOBAL CACHE ---
# Prevents authenticating and downloading the spreadsheet manifest 8x per run.
_cached_client = None
_cached_spreadsheet = None

def get_client():
    """Initializes and returns an authorized gspread client using environment variables."""
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
    """Returns the spreadsheet object, utilizing the global cache to save API quotas."""
    global _cached_spreadsheet
    if _cached_spreadsheet is not None:
        return _cached_spreadsheet
        
    client = get_client()
    _cached_spreadsheet = client.open_by_url(sheet_url)
    return _cached_spreadsheet

def _safe_get_records(sheet_url, sheet_names, retries=3, backoff=2.0):
    """
    Bulletproof helper to fetch records with automatic retries for ephemeral Google API 500/503 errors.
    Accepts a list of sheet names to handle schema naming variations smoothly.
    """
    spreadsheet = get_spreadsheet(sheet_url)
    
    for attempt in range(retries):
        for name in sheet_names:
            try:
                worksheet = spreadsheet.worksheet(name)
                return worksheet.get_all_records()
            except gspread.exceptions.WorksheetNotFound:
                continue # Try the next name variation
            except Exception as e:
                if attempt == retries - 1:
                    print(f"[ERROR] Failed to fetch '{name}' after {retries} attempts: {e}")
                else:
                    time.sleep(backoff * (attempt + 1))
                    
    return [] # Safe fallback instead of crashing the pipeline

# --- READ OPERATIONS (Now utilizing the cached, retry-enabled helper) ---

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
    return _safe_get_records(sheet_url, ["DailyMemory", "Daily Memory"])

def load_source_reliability(sheet_url, *args, **kwargs):
    return _safe_get_records(sheet_url, ["SourceReliability", "Source Reliability"])

def load_document_type_scores(sheet_url):
    return _safe_get_records(sheet_url, ["DocumentScores", "Document Scores"])

def get_system_settings(sheet_url):
    return _safe_get_records(sheet_url, ["Settings", "SystemSettings"])

def load_semantic_concepts(sheet_url):
    return _safe_get_records(sheet_url, ["Semantic Concepts", "SemanticConcepts"])

def load_event_statuses(sheet_url):
    return _safe_get_records(sheet_url, ["Event Status", "EventStatus"])

# --- WRITE OPERATIONS (Hardened against API exhaustion) ---

def append_to_research_queue(sheet_url, data_row):
    """Fallback single-row append. Highly recommend batch_append_to_research_queue instead."""
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
    """
    CRITICAL PERFORMANCE FIX: Appends multiple rows in a SINGLE API call.
    Prevents 429 RESOURCE_EXHAUSTED errors during high-volume news days.
    """
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
            
    # append_rows (plural) executes a single HTTP request for the entire block
    worksheet.append_rows(formatted_rows)

def log_unknown_event(sheet_url, *args, **kwargs):
    spreadsheet = get_spreadsheet(sheet_url)
    try:
        worksheet = spreadsheet.worksheet("UnknownEvents")
    except gspread.exceptions.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title="UnknownEvents", rows=1000, cols=5)
        worksheet.append_row(["Timestamp", "Title", "Source", "Raw Text"])
        
    # Example kwargs extraction mapping
    row_values = [
        kwargs.get("timestamp", ""),
        kwargs.get("article_title", ""),
        kwargs.get("Source", ""),
        str(kwargs.get("ai_response", ""))
    ]
    worksheet.append_row(row_values)

def update_last_checked(sheet_url, *args, **kwargs):
    pass # Reserved for future state tracking

def update_pipeline_metrics(sheet_url, *args, **kwargs):
    pass # Currently handled locally via SQLite

def batch_append_daily_memory(sheet_url, new_issuers):
    if not new_issuers:
        return
    spreadsheet = get_spreadsheet(sheet_url)
    try:
        worksheet = spreadsheet.worksheet("DailyMemory")
    except gspread.exceptions.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title="DailyMemory", rows=1000, cols=2)
        worksheet.append_row(["Issuer", "Timestamp"])
        
    import datetime
    ts = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S GMT")
    rows = [[issuer, ts] for issuer in new_issuers]
    worksheet.append_rows(rows)

def prune_daily_memory(sheet_url, *args, **kwargs):
    """Stub for daily cleanup if you move away from the SQLite intraday approach."""
    pass

def log_ontology_review(sheet_url, *args, **kwargs):
    pass

def aggregate_and_sync_yesterday(sheet_url, *args, **kwargs):
    pass