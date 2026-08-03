import os
import json
import sqlite3

from src.config.settings import SHEET_URL
from src.database import DB_PATH

def get_latest_run_from_db():
    """
    Fetches the most recent run metrics from the local SQLite observability database.
    Bulletproofed against Schema Drift: Uses SELECT * so missing columns don't crash the query.
    """
    if not os.path.exists(DB_PATH):
        print(f"[WARNING] Database file not found at {DB_PATH}")
        return None

    try:
        # Use a context manager (with block) to guarantee connection closure even on crash
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # SELECT * prevents "no such column" errors if the backend schema changes
            cursor.execute("""
                SELECT * FROM workflow_health
                ORDER BY timestamp DESC
                LIMIT 1
            """)
            row = cursor.fetchone()
            return dict(row) if row else None

    except sqlite3.OperationalError as e:
        if "no such table" in str(e).lower():
            print("[WARNING] Table 'workflow_health' does not exist yet. Skipping DB read.")
        else:
            print(f"[ERROR] SQLite OperationalError: {e}")
        return None
    except Exception as e:
        print(f"[ERROR] Failed to fetch latest run metrics from SQLite: {e}")
        return None

def sync_metrics_to_google_sheets(sheet_url=SHEET_URL):
    """Pushes the latest run metrics to the 'Metrics' tab of the Google Sheet."""
    metrics_data = get_latest_run_from_db()
    if not metrics_data:
        print("[WARNING] No run metrics found in database to sync.")
        return

    try:
        import gspread
        from google.oauth2.service_account import Credentials

        # Safely parse credentials from environment variable
        creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
        if creds_json:
            try:
                creds_dict = json.loads(creds_json)
            except json.JSONDecodeError:
                print("[ERROR] GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON. Halting sync.")
                return
                
            scopes = ["https://www.googleapis.com/auth/spreadsheets"]
            creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
            client = gspread.authorize(creds)
        else:
            # Fallback to default local auth file if configured in project
            if not os.path.exists("credentials.json"):
                print("[ERROR] No Google API credentials found in Env or file. Halting sync.")
                return
            client = gspread.service_account(filename="credentials.json")

        spreadsheet = client.open_by_url(sheet_url)
        
        # Ensure 'Metrics' tab exists, create if missing
        try:
            worksheet = spreadsheet.worksheet("Metrics")
        except gspread.exceptions.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title="Metrics", rows=1000, cols=10)
            worksheet.append_row([
                "Run ID", "Timestamp", "Success", "Failed", "Runtime (s)", 
                "Articles Processed", "Emails Sent", "Exception", "Workflow Version", "Run Number"
            ])

        # Format row data defensively. 
        # If a column doesn't exist in the DB, .get() safely returns "" instead of throwing a KeyError
        row_values = [
            metrics_data.get("run_id", ""),
            metrics_data.get("timestamp", ""),
            metrics_data.get("success", ""),
            metrics_data.get("failed", ""),
            metrics_data.get("runtime", ""),
            metrics_data.get("articles", ""),
            metrics_data.get("emails", ""),
            metrics_data.get("exception", ""),
            metrics_data.get("workflow_version", ""),
            metrics_data.get("run_number", "")
        ]

        worksheet.append_row(row_values)
        print(f"[SHEETS SYNC] Successfully synced run {metrics_data.get('run_id')} to Google Sheets 'Metrics' tab.")

    except ImportError:
        print("[ERROR] Missing required packages for Google Sheets. Run: pip install gspread google-auth")
    except Exception as e:
        print(f"[ERROR] Failed to sync metrics to Google Sheets: {e}")

if __name__ == "__main__":
    sync_metrics_to_google_sheets()