import json
import logging
from src.config.secrets import GOOGLE_SERVICE_ACCOUNT_JSON
from src.sheets import load_system_config
from monitor import get_google_credentials

logger = logging.getLogger(__name__)

creds = get_google_credentials()
SHEET_URL = "https://docs.google.com/spreadsheets/d/1vC3XqfK1l-U-HjC3O_0cIf_k4uQ3B3E7-T7U-A4-9W4/edit"
config_manifest = load_system_config(SHEET_URL, creds)
raw_pipeline_sheet = config_manifest.get("pipeline", [])
if raw_pipeline_sheet:
    sorted_stages = sorted([s for s in raw_pipeline_sheet if str(s.get("Active", "TRUE")).upper() == "TRUE"], key=lambda x: int(x.get("Order", 99)))
    execution_order = [s.get("Stage_ID") for s in sorted_stages]
    print("Execution Order from Sheet:", execution_order)
else:
    print("No pipeline sheet found.")
