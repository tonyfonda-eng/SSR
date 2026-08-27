import json
from src.sheets import load_pipeline_config
from src.config.settings import SHEET_URL

records = load_pipeline_config(SHEET_URL)
print(json.dumps(records, indent=2))
