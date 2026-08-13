from src.sheets import get_google_sheet
from src.config.settings import SHEET_URL

client, sheet = get_google_sheet(SHEET_URL)
ai_tab = sheet.worksheet("AI_Configs") if "AI_Configs" in [w.title for w in sheet.worksheets()] else None

if ai_tab:
    records = ai_tab.get_all_records()
    import json
    print(json.dumps(records, indent=2))
else:
    print("AI_Configs tab not found")
