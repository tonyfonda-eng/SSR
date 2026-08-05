import json

with open("docs/ingestion_ledger.json", "r") as f:
    history = json.load(f)

last_run_id = history[0]["run_id"] if history else None
current_run = [h for h in history if h.get("run_id") == last_run_id]

print(f"{'Source':<30} | {'Channel':<6} | {'Status':<10} | {'Raw':<5} | {'Parsed':<6} | {'Unique':<6} | {'Error'}")
print("-" * 100)
for entry in sorted(current_run, key=lambda x: (x.get("source", ""), x.get("channel", ""))):
    print(f"{entry.get('source',''):<30} | {entry.get('channel',''):<6} | {entry.get('status',''):<10} | {entry.get('raw_found',0):<5} | {entry.get('parsed_found',0):<6} | {entry.get('unique_found',0):<6} | {entry.get('error_message','')}")
