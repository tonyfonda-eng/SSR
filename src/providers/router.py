import json
import os

# Gmail API & SMTP Credentials
GMAIL_USER = os.environ.get("GMAIL_USER", "your-email@gmail.com")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "your-app-password")

def get_google_service_account():
    # Production / GitHub Actions: Load from Environment
    env_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if env_json:
        return json.loads(env_json)
    
    # Local / Agent Fallback: Load from ignored JSON file
    for filename in ["google_credentials.json", "secure_google_credentials.json"]:
        local_key_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), filename)
        if os.path.exists(local_key_path):
            with open(local_key_path, 'r') as f:
                return json.load(f)
                
    raise ValueError("Google Service Account credentials not found in environment, google_credentials.json, or secure_google_credentials.json")