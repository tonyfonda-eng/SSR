import subprocess
import json
import re
from datetime import datetime

# 1. Get recent runs
try:
    result = subprocess.run(["gh", "run", "list", "--workflow=monitor.yml", "--limit=10", "--json", "databaseId,createdAt"], capture_output=True, text=True)
    runs = json.loads(result.stdout)
except Exception as e:
    print(f"Error fetching runs: {e}")
    exit(1)

print(f"Found {len(runs)} recent runs.")
# We will just parse the last run to see the format, then scale up
run_id = runs[0]['databaseId']
result = subprocess.run(["gh", "run", "view", str(run_id), "--log"], capture_output=True, text=True)
logs = result.stdout

for line in logs.split('\n'):
    if "PIPELINE ECONOMICS" in line or "DEDUPE_HASH" in line or "AI_TICKER_RESOLUTION" in line or "ONTOLOGY_CONCEPTS" in line or "EXCLUDE_GLOBAL_KEYWORDS" in line:
        print(line)

