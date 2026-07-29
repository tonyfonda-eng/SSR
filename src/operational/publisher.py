import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build

class GoogleSheetsPublisher:
    """Manages secure OAuth2 connections and flushes projection layers to Google Sheets."""
    
    def __init__(self, spreadsheet_id: str, credentials, store, serializer):
        self.spreadsheet_id = spreadsheet_id
        self.store = store
        self.serializer = serializer
        self.logger = logging.getLogger("SSR.GooglePublisher")
        
        cred_path = "google_credentials.json"
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        
        try:
            self.creds = service_account.Credentials.from_service_account_file(
                cred_path, scopes=scopes
            )
            self.service = build("sheets", "v4", credentials=self.creds)
            self.logger.info("Authenticated Google Sheets API client session via Service Account.")
        except Exception as e:
            self.logger.error(f"Failed to initialize Google Sheets API authorization: {str(e)}")
            raise e

    def publish_sheet(self, sheet_name: str):
        """Fetches SQLite row documents, converts via serializer, and updates Google grid."""
        rows = self.store.get_sheet_rows(sheet_name)
        if not rows:
            return

        matrix = self.serializer.serialize(sheet_name, rows)
        body = {"values": matrix}
        
        try:
            self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=f"'{sheet_name}'!A1",
                valueInputOption="RAW",
                body=body
            ).execute()
            self.logger.info(f"Successfully synchronized {len(matrix)} rows to Google Sheet: [{sheet_name}]")
        except Exception as e:
            error_msg = str(e).lower()
            # Catching BOTH possible missing-tab exceptions from Google's API
            if "not found" in error_msg or "unable to parse range" in error_msg:
                self.logger.warning(f"Tab '{sheet_name}' missing. Initiating auto-creation sequence...")
                self._create_tab(sheet_name)
                
                # Retry update once tab structure exists
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"'{sheet_name}'!A1",
                    valueInputOption="RAW",
                    body=body
                ).execute()
                self.logger.info(f"Successfully synchronized {len(matrix)} rows to Google Sheet: [{sheet_name}]")
            else:
                raise e

    def _create_tab(self, sheet_name: str):
        """Auto-creates missing worksheet tabs dynamically inside the workbook."""
        batch_update_request_body = {
            "requests": [{
                "addSheet": {
                    "properties": {
                        "title": sheet_name,
                        "gridProperties": {"rowCount": 1000, "columnCount": 26}
                    }
                }
            }]
        }
        self.service.spreadsheets().batchUpdate(
            spreadsheetId=self.spreadsheet_id,
            body=batch_update_request_body
        ).execute()
        self.logger.info(f"Created dynamic worksheet tab: {sheet_name}")
