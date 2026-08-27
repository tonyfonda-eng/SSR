import json
from src.sheets import load_pipeline_config
from src.config.settings import SHEET_URL

records = load_pipeline_config(SHEET_URL)
active_stages = [r for r in records if str(r.get("Active", "")).upper() == "TRUE"]
for r in active_stages:
    print(f"Order: {r.get('Order')}, Stage_ID: {r.get('Stage_ID')}")
