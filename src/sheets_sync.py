import datetime
import sqlite3
from src.config.settings import SHEET_URL

def get_latest_run_from_db():
    """Fetches the most recent run metrics from the local SQLite observability database."""
    conn = sqlite3.connect("ssr_observability.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT run_id, timestamp, success, failed, runtime, articles, emails, exception, workflow_version, run_number
            FROM workflow_health
            ORDER BY timestamp DESC
            LIMIT 1
        """)
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        print(f"[ERROR] Failed to fetch latest run metrics from SQLite: {e}")
        return None
    finally:
        conn.close()


def sync_metrics_to_google_sheets(sheet_url=SHEET_URL):
    """Pushes the latest run metrics to the 'Metrics' tab of the Google Sheet."""
    metrics_data = get_latest_run_from_db()
    if not metrics_data:
        print("[WARNING] No run metrics found in database to sync.")
        return

    try:
        import gspread
        from google.oauth2.service_account import Credentials
        import os
        import json

        creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
        if creds_json:
            creds_dict = json.loads(creds_json)
            scopes = ["https://www.googleapis.com/auth/spreadsheets"]
            creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
            client = gspread.authorize(creds)
        else:
            client = gspread.service_account(filename="credentials.json")

        spreadsheet = client.open_by_url(sheet_url)
        
        try:
            worksheet = spreadsheet.worksheet("Metrics")
        except gspread.exceptions.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title="Metrics", rows=1000, cols=10)
            worksheet.append_row([
                "Run ID", "Timestamp", "Success", "Failed", "Runtime (s)", 
                "Articles Processed", "Emails Sent", "Exception", "Workflow Version", "Run Number"
            ])

        row_values = [
            metrics_data.get("run_id"),
            metrics_data.get("timestamp"),
            metrics_data.get("success"),
            metrics_data.get("failed"),
            metrics_data.get("runtime"),
            metrics_data.get("articles"),
            metrics_data.get("emails"),
            metrics_data.get("exception", ""),
            metrics_data.get("workflow_version"),
            metrics_data.get("run_number")
        ]

        worksheet.append_row(row_values)
        print(f"[SHEETS SYNC] Successfully synced run {metrics_data.get('run_id')} to Google Sheets 'Metrics' tab.")

    except Exception as e:
        print(f"[ERROR] Failed to sync metrics to Google Sheets: {e}")


if __name__ == "__main__":
    sync_metrics_to_google_sheets()