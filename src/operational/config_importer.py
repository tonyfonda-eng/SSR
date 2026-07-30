import hashlib
import json
from typing import Dict, Any, List
from googleapiclient.discovery import build
from src.engine.transport import PayloadError

class ConfigurationImporter:
    """Pulls human configuration records from the sheet and sanitizes them before DAG promotion."""
    
    def __init__(self, spreadsheet_id: str, credentials):
        self.spreadsheet_id = spreadsheet_id
        self.service = build('sheets', 'v4', credentials=credentials)

    def fetch_and_sanitize(self) -> Dict[str, Any]:
        """Polls sheet 08_Configuration and converts the A1 matrix into a typed configuration state."""
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range="08_Configuration!A2:C50"
            ).execute()
        except Exception as e:
            raise PayloadError(f"Failed to fetch configuration sheet over network: {str(e)}")

        rows = result.get('values', [])
        raw_config = {}

        for row in rows:
            if len(row) < 2: continue
            key = row[0].strip()
            val = row[1].strip()
            val_type = row[2].strip().lower() if len(row) > 2 else "string"

            # Strict Boundary Coercion - Prevent injection strings from breaking python runtime fields
            try:
                if val_type == "bool":
                    raw_config[key] = val.upper() in ("TRUE", "1", "YES")
                elif val_type == "float":
                    raw_config[key] = float(val)
                elif val_type == "int":
                    raw_config[key] = int(val)
                elif val_type == "list":
                    raw_config[key] = [item.strip() for item in val.split(",") if item.strip()]
                else:
                    raw_config[key] = val
            except ValueError:
                # If a human enters a string into a float slot, isolate the parameter to prevent crashes
                raw_config[key] = None

        # Generate the unique cryptographic stamp for this specific configuration state
        config_bytes = json.dumps(raw_config, sort_keys=True).encode()
        raw_config["_config_hash"] = hashlib.sha256(config_bytes).hexdigest()

        return raw_config
