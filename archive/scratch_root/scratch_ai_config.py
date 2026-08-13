from src.sheets import load_ai_configurations
from src.config.settings import SHEET_URL
import json

ai_configs = load_ai_configurations(SHEET_URL)
print(json.dumps(ai_configs, indent=2))
