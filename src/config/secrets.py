import json
import os


def get_google_service_account():
    # Production / GitHub Actions: Load from Environment
    env_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if env_json:
        return json.loads(env_json)
    
    # Local / Agent Fallback: Load from ignored JSON file
    local_key_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "google_credentials.json")
    if os.path.exists(local_key_path):
        with open(local_key_path, 'r') as f:
            return json.load(f)
            
    raise ValueError("Google Service Account credentials not found in environment or google_credentials.json")
