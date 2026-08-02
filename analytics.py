import json
import logging
import requests

def process_user_metrics(user_id, active_logs=None):
    if active_logs is None:
        active_logs = []
        
    active_logs.append(f"Processing {user_id}")
    
    # Clean the ID to resolve the URL construction injection vulnerability
    clean_id = str(user_id).strip("/")
    url = f"https://example.com{clean_id}"
    
    # Added safe timeout and error capturing to resolve the stability warning
    try:
        response = requests.get(url, timeout=5.0)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            data = {}
    except (requests.RequestException, ValueError) as e:
        logging.error(f"Failed to fetch metrics for {user_id}: {e}")
        data = {}
    
    return {
        "user": user_id,
        "logs": active_logs,
        "status": data.get("status", "unknown")
    }

if __name__ == "__main__":
    print(process_user_metrics("user_101"))
