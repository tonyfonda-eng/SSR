import os
import json
import time
import datetime
import ast
import warnings
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
        # If it's a Python literal-encoded string, decode (with warning suppression)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", SyntaxWarning)
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
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", SyntaxWarning)
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
                # ---------------------------------------------------------
                # AUDIT FIX: Robust manual header parsing to prevent gspread
                # from crashing on duplicate or empty [''] header columns.
                # ---------------------------------------------------------
                raw_values = worksheet.get_all_values()
                if not raw_values:
                    return []
                    
                headers = raw_values[0]
                unique_headers = []
                seen = set()
                
                for i, h in enumerate(headers):
                    h_str = str(h).strip()
                    if not h_str or h_str in seen:
                        h_str = f"Unnamed_Col_{i+1}"
                    seen.add(h_str)
                    unique_headers.append(h_str)
                    
                records = []
                for row in raw_values[1:]:
                    # Pad the row if it's shorter than the headers array
                    padded_row = row + [""] * (len(unique_headers) - len(row))
                    # Only add rows that actually contain data
                    if any(str(v).strip() for v in padded_row):
                        records.append(dict(zip(unique_headers, padded_row)))
                        
                return records
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

def load_audit_protocol(sheet_url):
    """Fetches the dynamic auditing protocol from Google Sheets."""
    return _safe_get_records(sheet_url, ["Audit Protocol", "AuditingProtocol"])

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

def batch_update_last_checked(sheet_url, source_names):
    if not source_names:
        return
    spreadsheet = get_spreadsheet(sheet_url)
    try:
        worksheet = spreadsheet.worksheet("Sources")
    except gspread.exceptions.WorksheetNotFound:
        return
        
    try:
        # Get all values to find rows efficiently in memory instead of multiple API calls
        all_values = worksheet.get_all_values()
        if not all_values: return
        
        headers = all_values[0]
        col_index = None
        for i, header in enumerate(headers):
            if "checked" in header.lower() or "timestamp" in header.lower():
                col_index = i
                break
                
        if col_index is None: return
        
        ts = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S GMT")
        cells_to_update = []
        source_set = set(source_names)
        
        # Find which rows match the successful sources (assuming Source is column index 2)
        source_col_idx = None
        for i, h in enumerate(headers):
            if "source" in h.lower() and "name" not in h.lower() and "url" not in h.lower():
                source_col_idx = i
                break
        if source_col_idx is None:
            source_col_idx = 2 # fallback to index 2
            
        for row_idx, row in enumerate(all_values):
            if row_idx == 0: continue
            if len(row) > source_col_idx and row[source_col_idx].strip() in source_set:
                cells_to_update.append(gspread.Cell(row=row_idx+1, col=col_index+1, value=ts))
                
        if cells_to_update:
            worksheet.update_cells(cells_to_update)
    except Exception as e:
        print(f"Failed batch update last checked: {e}")


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
def batch_update_source_telemetry(sheet_url, ingestion_ledger):
    """
    Updates the parsing metrics in the Sources sheet.
    ingestion_ledger: list of dicts, each with 'source' and 'raw_found' (or 'unique_found')
    """
    if not ingestion_ledger:
        return
        
    spreadsheet = get_spreadsheet(sheet_url)
    try:
        worksheet = spreadsheet.worksheet('Sources')
        all_values = worksheet.get_all_values()
    except Exception as e:
        print(f"[SHEET ERROR] Could not fetch Sources sheet for telemetry: {e}")
        return
        
    if not all_values or len(all_values) < 2:
        return
        
    headers = all_values[0]
    
    # Locate columns
    source_col_idx = None
    parsed_col_idx = None
    cumulative_col_idx = None
    
    for i, h in enumerate(headers):
        h_lower = h.lower()
        if "source" in h_lower and "name" not in h_lower and "url" not in h_lower:
            source_col_idx = i
        elif "parsed (last run)" in h_lower:
            parsed_col_idx = i
        elif "cumulative parsed (today)" in h_lower:
            cumulative_col_idx = i
            
    if source_col_idx is None or parsed_col_idx is None or cumulative_col_idx is None:
        print("[SHEET ERROR] Could not locate telemetry columns in Sources sheet.")
        return
        
    # Map ledger to a dictionary
    ledger_map = {}
    for entry in ingestion_ledger:
        src = entry.get("source")
        if src:
            # Aggregate if there are multiple entries for the same source
            ledger_map[src] = ledger_map.get(src, 0) + entry.get("parsed_found", entry.get("raw_found", 0))
            
    cells_to_update = []
    
    for row_idx, row in enumerate(all_values):
        if row_idx == 0:
            continue
            
        if len(row) > source_col_idx:
            src = row[source_col_idx].strip()
            if src in ledger_map:
                new_parsed = ledger_map[src]
                
                # Current cumulative
                current_cum_str = row[cumulative_col_idx].strip() if len(row) > cumulative_col_idx else "0"
                try:
                    current_cum = int(current_cum_str) if current_cum_str.isdigit() else 0
                except:
                    current_cum = 0
                    
                new_cum = current_cum + new_parsed
                
                # Append cell updates
                cells_to_update.append(gspread.Cell(row=row_idx + 1, col=parsed_col_idx + 1, value=new_parsed))
                cells_to_update.append(gspread.Cell(row=row_idx + 1, col=cumulative_col_idx + 1, value=new_cum))
                
    if cells_to_update:
        try:
            worksheet.update_cells(cells_to_update)
            print(f"[TELEMETRY] Successfully pushed parsing metrics for {len(ledger_map)} sources.")
        except Exception as e:
            print(f"[SHEET ERROR] Failed to push telemetry updates: {e}")
def prune_daily_memory(sheet_url, *args, **kwargs): pass
def log_ontology_review(sheet_url, *args, **kwargs): pass
def aggregate_and_sync_yesterday(sheet_url, *args, **kwargs): pass