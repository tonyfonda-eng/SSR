import json
import os

# Gmail API & SMTP Credentials
GMAIL_USER = os.environ.get("GMAIL_USER", "your-email@gmail.com")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "your-app-password")

def get_google_service_account():
    creds_dict = None
    
    # Production / GitHub Actions: Load from Environment
    env_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if env_json:
        try:
            creds_dict = json.loads(env_json)
        except json.JSONDecodeError:
            pass
    
    # Local / Agent Fallback: Load from ignored JSON file
    if not creds_dict:
        for filename in ["google_credentials.json", "secure_google_credentials.json"]:
            local_key_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), filename)
            if os.path.exists(local_key_path):
                with open(local_key_path, 'r', encoding='utf-8') as f:
                    creds_dict = json.load(f)
                break
                
    if not creds_dict:
        raise ValueError("Google Service Account credentials not found in environment, google_credentials.json, or secure_google_credentials.json")

    # --- BULLETPROOF PEM PRIVATE KEY SANITIZATION ---
    if "private_key" in creds_dict:
        pk = str(creds_dict["private_key"])
        # Unescape literal backslashes into true cryptographic newlines
        pk = pk.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\\\n", "\n")
        if not pk.endswith("\n"):
            pk += "\n"
        creds_dict["private_key"] = pk

    return creds_dict