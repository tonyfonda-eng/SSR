from src.sheets import get_system_settings
from src.config.settings import SHEET_URL
import json

settings = get_system_settings(SHEET_URL)
print(json.dumps(settings, indent=2))
