import os
import json
import time
import datetime
import ast
import gspread
from google.oauth2.service_account import Credentials
from src.config.secrets import get_google_service_account

_cached_client = None
_cached_spreadsheet = None

def _sanitize_private_key(raw_pk: str) -> str:
    # Normalize to Python string
    if isinstance(raw_pk, bytes):
        pk = raw_pk.decode("utf-8", "strict")
    else:
        pk = str(raw_pk)

    # Quick accept: already valid PEM
    if pk.startswith("-----BEGIN ") and "-----END " in pk:
        pk = pk.strip()
        if not pk.endswith("\n"):
            pk += "\n"
        return pk

    # Remove accidental surrounding quotes
    if (pk.startswith('"') and pk.endswith('"')) or (pk.startswith("'") and pk.endswith("'")):
        pk = pk[1:-1]

    # Iteratively try to unwrap encodings/escapes (handles double-encoded cases)
    for _ in range(5):
        prev = pk
        # If it's a JSON-encoded string, decode
        try:
            decoded = json.loads(pk)
            if isinstance(decoded, str):
                pk = decoded
        except Exception:
            pass
        # If it's a Python literal-encoded string, decode
        try:
            decoded = ast.literal_eval(pk)
            if isinstance(decoded, str):
                pk = decoded
        except Exception:
            pass
        # Replace common escaped newline sequences (more-escaped first)
        pk = pk.replace("\\r\\n", "\n").replace("\\\\n", "\n").replace("\\n", "\n")
        # stop if nothing changed
        if pk == prev:
            break

    # Last-resort: decode escape sequences (use cautiously)
    if ("\\n" in pk or "\\\\" in pk) and not (pk.startswith("-----BEGIN ") and "-----END " in pk):
        try:
            pk_candidate = pk.encode("utf-8").decode("unicode_escape")
            pk = pk_candidate
        except Exception:
            # leave as-is; we will validate below and raise if malformed
            pass

    # Trim and sanity-check framing
    pk = pk.strip()
    if not pk.startswith("-----BEGIN ") or "-----END " not in pk:
        raise ValueError("private_key appears malformed after sanitization (missing PEM header/footer)")

    if not pk.endswith("\n"):
        pk += "\n"

    # Validate PEM by attempting to parse it (fails fast with clearer message)
    try:
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        from cryptography.hazmat.backends import default_backend
        load_pem_private_key(pk.encode("utf-8"), password=None, backend=default_backend())
    except Exception as e:
        # Do NOT include the key in the error message
        raise ValueError(f"private_key failed PEM parse validation after sanitization: {e}")

    return pk

def get_client():
    global _cached_client
    if _cached_client is not None:
        return _cached_client
        
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    
    # Retrieve credentials dictionary through the centralized secrets manager
    creds_dict = get_google_service_account()

    # If credentials returned as a string, parse to dict
    if isinstance(creds_dict, str):
        try:
            creds_dict = json.loads(creds_dict)
        except json.JSONDecodeError:
            creds_dict = ast.literal_eval(creds_dict)

    # --- PRIVATE KEY SANITIZATION & VALIDATION ---
    if creds_dict and "private_key" in creds_dict:
        creds_dict["private_key"] = _sanitize_private_key(creds_dict["private_key"])

    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    _cached_client = gspread.authorize(creds)
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

# =====================================================================
# CONFIGURATION LOADERS (Granular Breakdown)
# =====================================================================

def load_rules(sheet_url):
    return _safe_get_records(sheet_url, ["Rules", "RegexRules"])

def load_sources(sheet_url):
    return _safe_get_records(sheet_url, ["Sources"])

def load_playbooks(sheet_url):
    return _safe_get_records(sheet_url, ["Playbooks", "StrategyPlaybooks"])

def load_global_exclusions(sheet_url):
    return _safe_get_records(sheet_url, ["GlobalExclusions", "Global Exclusions"])

def load_gold_standards(sheet_url):
    return _safe_get_records(sheet_url, ["GoldStandards", "Gold Standards"])

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

def load_pipeline_config(sheet_url):
    """Fetches the highly granular adaptive execution order from the 'Pipeline' tab."""
    return _safe_get_records(sheet_url, ["Pipeline", "Process", "Execution Pipeline"])

def load_ai_configurations(sheet_url):
    """Fetches specific granular settings for AI Inference stages."""
    return _safe_get_records(sheet_url, ["AI Configs", "AI Prompts"])

def load_financial_constraints(sheet_url):
    """Fetches specific granular constraints for Strategy Engine stages."""
    return _safe_get_records(sheet_url, ["Financial Rules", "Constraints"])

# =====================================================================
# STATE MANAGEMENT
# =====================================================================

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

# Backward Compatibility Stubs
def update_pipeline_metrics(sheet_url, *args, **kwargs): pass 
def prune_daily_memory(sheet_url, *args, **kwargs): pass
def log_ontology_review(sheet_url, *args, **kwargs): pass
def aggregate_and_sync_yesterday(sheet_url, *args, **kwargs): pass