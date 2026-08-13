import json
import datetime
today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
with open("docs/ingestion_ledger.json", "r") as f:
    ledger = json.load(f)
    today_ledger = [x for x in ledger if x.get("timestamp", "").startswith(today)]
source_entries = [x for x in today_ledger if x.get("source", "").upper() == "LSE.CO.UK"]
latest_ledger = sorted(source_entries, key=lambda x: x.get("timestamp", ""))[-1]
print("LATEST:", latest_ledger.get("termination_reason"), latest_ledger.get("timestamp"))
