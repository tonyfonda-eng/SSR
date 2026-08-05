from src.config.settings import SHEET_URL
from src.sheets import load_sources
import json

sources = load_sources(SHEET_URL)
print(json.dumps(sources, indent=2))
