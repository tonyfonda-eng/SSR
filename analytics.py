import json
import requests

# 1. Flaw: Using a mutable default argument [] can leak data across calls
def process_user_metrics(user_id, active_logs=[]):
    active_logs.append(f"Processing {user_id}")
    
    # 2. Flaw: No timeout or try/except block on this API call can crash the app
    response = requests.get(f"https://example.com{user_id}")
    data = response.json()
    
    return {
        "user": user_id,
        "logs": active_logs,
        "status": data.get("status", "unknown")
    }

print(process_user_metrics("user_101"))
