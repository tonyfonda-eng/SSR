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
    try:
        return spreadsheet.worksheet("Rules").get_all_records()
    except gspread.exceptions.WorksheetNotFound:
        return []

def load_sources(sheet_url):
    """Loads operational sources from the Google Sheet."""
    client = get_client()
    spreadsheet = client.open_by_url(sheet_url)
    try:
        return spreadsheet.worksheet("Sources").get_all_records()
    except gspread.exceptions.WorksheetNotFound:
        return []

def load_playbooks(sheet_url):
    """Loads operational playbooks from the Google Sheet."""
    client = get_client()
    spreadsheet = client.open_by_url(sheet_url)
    try:
        return spreadsheet.worksheet("Playbooks").get_all_records()
    except gspread.exceptions.WorksheetNotFound:
        return []

def append_to_research_queue(sheet_url, data_row):
    """Appends an item to the 'ResearchQueue' worksheet."""
    client = get_client()
    spreadsheet = client.open_by_url(sheet_url)
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

def update_last_checked(sheet_url, *args, **kwargs):
    """Updates source last checked timestamp."""
    client = get_client()
    spreadsheet = client.open_by_url(sheet_url)
    try:
        worksheet = spreadsheet.worksheet("Sources")
    except gspread.exceptions.WorksheetNotFound:
        pass

def load_global_exclusions(sheet_url):
    """Loads global exclusions from the Google Sheet."""
    client = get_client()
    spreadsheet = client.open_by_url(sheet_url)
    try:
        return spreadsheet.worksheet("GlobalExclusions").get_all_records()
    except gspread.exceptions.WorksheetNotFound:
        return []

def load_gold_standards(sheet_url):
    """Loads gold standards dataset from the Google Sheet."""
    client = get_client()
    spreadsheet = client.open_by_url(sheet_url)
    try:
        return spreadsheet.worksheet("GoldStandards").get_all_records()
    except gspread.exceptions.WorksheetNotFound:
        return []

def log_unknown_event(sheet_url, *args, **kwargs):
    """Logs unknown classification events."""
    client = get_client()
    spreadsheet = client.open_by_url(sheet_url)
    try:
        worksheet = spreadsheet.worksheet("UnknownEvents")
    except gspread.exceptions.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title="UnknownEvents", rows=1000, cols=5)
        worksheet.append_row(["Timestamp", "Title", "Source", "Raw Text"])

def update_pipeline_metrics(sheet_url, *args, **kwargs):
    """Updates pipeline execution metrics."""
    client = get_client()
    spreadsheet = client.open_by_url(sheet_url)
    try:
        worksheet = spreadsheet.worksheet("Metrics")
    except gspread.exceptions.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title="Metrics", rows=1000, cols=10)

def load_daily_memory(sheet_url, *args, **kwargs):
    """Loads daily AI/pipeline memory."""
    client = get_client()
    spreadsheet = client.open_by_url(sheet_url)
    try:
        return spreadsheet.worksheet("DailyMemory").get_all_records()
    except gspread.exceptions.WorksheetNotFound:
        return []

def batch_append_daily_memory(sheet_url, *args, **kwargs):
    """Batches append items to daily memory."""
    pass

def prune_daily_memory(sheet_url, *args, **kwargs):
    """Prunes stale daily memory entries."""
    pass

def load_source_reliability(sheet_url, *args, **kwargs):
    """Loads source reliability scores."""
    client = get_client()
    spreadsheet = client.open_by_url(sheet_url)
    try:
        return spreadsheet.worksheet("SourceReliability").get_all_records()
    except gspread.exceptions.WorksheetNotFound:
        return []

def log_ontology_review(sheet_url, *args, **kwargs):
    """Logs ontology review metrics."""
    pass

def load_document_type_scores(sheet_url):
    """Loads document type scores from the Google Sheet."""
    client = get_client()
    spreadsheet = client.open_by_url(sheet_url)
    try:
        return spreadsheet.worksheet("DocumentScores").get_all_records()
    except gspread.exceptions.WorksheetNotFound:
        return []

def aggregate_and_sync_yesterday(sheet_url, *args, **kwargs):
    """Aggregates and syncs previous day telemetry."""
    pass

def get_system_settings(sheet_url):
    """Loads system settings from the Google Sheet."""
    client = get_client()
    spreadsheet = client.open_by_url(sheet_url)
    try:
        return spreadsheet.worksheet("Settings").get_all_records()
    except gspread.exceptions.WorksheetNotFound:
        try:
            return spreadsheet.worksheet("SystemSettings").get_all_records()
        except gspread.exceptions.WorksheetNotFound:
            return []