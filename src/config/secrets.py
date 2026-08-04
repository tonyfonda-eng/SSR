import os
import json
import re
import ast

# Gmail API & SMTP Credentials
GMAIL_USER = os.environ.get("GMAIL_USER", "your-email@gmail.com")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "your-app-password")

def _sanitize_private_key(raw_pk: str) -> str:
    # Normalize to text
    if isinstance(raw_pk, bytes):
        pk = raw_pk.decode("utf-8", "strict")
    else:
        pk = str(raw_pk)

    # Quick trims and unquote
    pk = pk.strip()
    if (pk.startswith('"') and pk.endswith('"')) or (pk.startswith("'") and pk.endswith("'")):
        pk = pk[1:-1]

    # Expand common escape sequences (handles \n, \\n, etc.)
    pk = pk.replace("\\r\\n", "\n").replace("\\\\n", "\n").replace("\\n", "\n")

    # If there are still escaped forms, try a conservative unicode_escape as a last resort
    if ("\\n" in pk or "\\\\" in pk) and not (pk.startswith("-----BEGIN ") and "-----END " in pk):
        try:
            pk = pk.encode("utf-8").decode("unicode_escape")
        except Exception:
            pass

    pk = pk.strip()

    # Now ensure header/footer exist
    header_match = re.search(r"(-----BEGIN [^\n]+-----)", pk)
    footer_match = re.search(r"(-----END [^\n]+-----)", pk)
    if not header_match or not footer_match:
        raise ValueError("private_key appears malformed (missing PEM header/footer)")

    header = header_match.group(1)
    footer = footer_match.group(1)

    # Extract the base64 body between header and footer
    body_match = re.search(r"-----BEGIN [^\n]+-----\s*(.*?)\s*-----END [^\n]+-----", pk, re.S)
    if not body_match:
        raise ValueError("private_key PEM body not found")

    body = body_match.group(1)

    # Remove any characters that are not valid in base64 (including stray backslashes, spaces, etc.)
    body_clean = re.sub(r"[^A-Za-z0-9+/=]", "", body)

    if not body_clean:
        raise ValueError("private_key PEM body empty after cleaning")

    # Rewrap into 64-character lines (standard PEM formatting)
    wrapped = "\n".join([body_clean[i:i+64] for i in range(0, len(body_clean), 64)])

    # Reconstruct the PEM and ensure trailing newline
    pk_clean = f"{header}\n{wrapped}\n{footer}\n"

    # Final minimal validation: attempt to parse using cryptography (fails fast)
    try:
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        from cryptography.hazmat.backends import default_backend
        load_pem_private_key(pk_clean.encode("utf-8"), password=None, backend=default_backend())
    except Exception as e:
        raise ValueError(f"private_key failed PEM parse validation after cleaning: {e}")

    return pk_clean

def get_google_service_account():
    creds_dict = None
    
    # Production / GitHub Actions: Load from Environment
    env_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if env_json:
        try:
            creds_dict = json.loads(env_json)
        except json.JSONDecodeError:
            try:
                creds_dict = ast.literal_eval(env_json)
            except Exception:
                pass
    
    # Local / Agent Fallback: Load from ignored JSON file
    if not creds_dict:
        for filename in ["google_credentials.json", "secure_google_credentials.json", "credentials.json"]:
            local_key_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), filename)
            if os.path.exists(local_key_path):
                with open(local_key_path, 'r', encoding='utf-8') as f:
                    creds_dict = json.load(f)
                break
                
    if not creds_dict:
        raise ValueError("Google Service Account credentials not found in environment or local credential files.")

    if "private_key" in creds_dict:
        creds_dict["private_key"] = _sanitize_private_key(creds_dict["private_key"])

    return creds_dict