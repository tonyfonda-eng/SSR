import json

try:
    with open('docs/ingestion_ledger.json', 'r') as f:
        ledger = json.load(f)
    
    runs = {}
    for item in ledger:
        run_id = item.get('run_id')
        if run_id not in runs:
            runs[run_id] = 0
        runs[run_id] += item.get('dedupe_passed_count', 0)
    
    today_runs = {k: v for k, v in runs.items() if '20260814' in k}
    total_today = sum(today_runs.values())
    
    print(f"Total new articles passed dedupe today (2026-08-14): {total_today}")
    if today_runs:
        print("Breakdown by run:")
        for r, c in today_runs.items():
            print(f"  {r}: {c}")
    else:
        print("No runs recorded with '20260814' in run_id")
        
except Exception as e:
    print(f"Error: {e}")
