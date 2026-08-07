from src.sheets import _safe_get_records
from src.config.settings import SHEET_URL
import json

ai_configs = _safe_get_records(SHEET_URL, ["AI Configs", "AI Models"])
print("AI Configs:")
print(json.dumps(ai_configs, indent=2))
