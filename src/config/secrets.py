import json
import os
import ast

# Gmail API & SMTP Credentials
GMAIL_USER = os.environ.get("GMAIL_USER", "your-email@gmail.com")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "your-app-password")


def _sanitize_private_key(raw_pk: str) -> str:
    """Normalize a possibly-escaped PEM private key into a clean PEM string.

    This handles values coming from environment variables (raw JSON, double-encoded JSON,
    or Python-literal strings) and local JSON files. It iteratively un-wraps JSON/Python
    quoting and collapses common escape sequences like "\\n" into real newlines.
    """
    if isinstance(raw_pk, bytes):
        pk = raw_pk.decode("utf-8", "strict")
    else:
        pk = str(raw_pk)

    # Remove accidental surrounding quotes
    if (pk.startswith('"') and pk.endswith('"')) or (pk.startswith("'") and pk.endswith("'")):
        pk = pk[1:-1]

    # Iteratively try to unwrap JSON/Python quoting and collapse escaped newlines
    for _ in range(5):
        prev = pk
        try:
            decoded = json.loads(pk)
            if isinstance(decoded, str):
                pk = decoded
        except Exception:
            pass
        try:
            decoded = ast.literal_eval(pk)
            if isinstance(decoded, str):
                pk = decoded
        except Exception:
            pass
        pk = pk.replace("\\r\\n", "\n").replace("\\\\n", "\n").replace("\\n", "\n")
        if pk == prev:
            break

    # Last-resort: decode escape sequences (use carefully)
    if ("\\n" in pk or "\\\\" in pk) and not (pk.startswith("-----BEGIN ") and "-----END " in pk):
        try:
            pk_candidate = pk.encode("utf-8").decode("unicode_escape")
            pk = pk_candidate
        except Exception:
            pass

    pk = pk.strip()
    if not pk.startswith("-----BEGIN ") or "-----END " not in pk:
        raise ValueError("private_key appears malformed after sanitization (missing PEM header/footer)")

    if not pk.endswith("\n"):
        pk += "\n"

    return pk


def get_google_service_account():
    """Return a credentials dict for a Google service account.

    Sources checked (in order):
    - Environment variable GOOGLE_SERVICE_ACCOUNT_JSON (robust parsing of raw or double-encoded JSON)
    - Local files: google_credentials.json, secure_google_credentials.json (located two levels up from this file)

    The returned dict will have a sanitized "private_key" suitable for google-auth.
    """
    creds_dict = None

    env_raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if env_raw:
        try:
            parsed = json.loads(env_raw)
            if isinstance(parsed, str):
                try:
                    creds_dict = json.loads(parsed)
                except json.JSONDecodeError:
                    try:
                        creds_dict = ast.literal_eval(parsed)
                    except Exception:
                        creds_dict = parsed
            else:
                creds_dict = parsed
        except json.JSONDecodeError:
            try:
                creds_dict = ast.literal_eval(env_raw)
            except Exception:
                creds_dict = env_raw

    # Local file fallback
    if not creds_dict:
        for filename in ["google_credentials.json", "secure_google_credentials.json"]:
            local_key_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), filename)
            if os.path.exists(local_key_path):
                with open(local_key_path, 'r', encoding='utf-8') as f:
                    creds_dict = json.load(f)
                break

    if not creds_dict:
        raise ValueError("Google Service Account credentials not found in environment or local files")

    # Coerce to dict if it's still a string
    if isinstance(creds_dict, str):
        try:
            creds_dict = json.loads(creds_dict)
        except Exception:
            try:
                creds_dict = ast.literal_eval(creds_dict)
            except Exception:
                pass

    if not isinstance(creds_dict, dict):
        raise ValueError("Failed to parse Google service account credentials into a dict")

    if "private_key" in creds_dict:
        creds_dict["private_key"] = _sanitize_private_key(creds_dict["private_key"])

    return creds_dict
