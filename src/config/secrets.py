import os
import json
import ast
import re

# Gmail API & SMTP Credentials
GMAIL_USER = os.environ.get("GMAIL_USER", "your-email@gmail.com")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "your-app-password")


def _sanitize_private_key(raw_pk: str) -> str:
    """Normalize and repair a possibly-escaped or corrupted PEM private key.

    This routine:
    - Converts common escaped newline sequences to real newlines.
    - Unwraps JSON/Python quoting layers if present.
    - Extracts the base64 body and removes any non-base64 characters (including stray backslashes).
    - Re-wraps the base64 into 64-character lines and reconstructs a canonical PEM.
    - Validates the result by attempting to parse it with cryptography.
    """
    if isinstance(raw_pk, bytes):
        pk = raw_pk.decode("utf-8", "strict")
    else:
        pk = str(raw_pk)

    # Trim and remove accidental surrounding quotes
    pk = pk.strip()
    if (pk.startswith('"') and pk.endswith('"')) or (pk.startswith("'") and pk.endswith("'")):
        pk = pk[1:-1]

    # Unwrap common escape sequences and repeated encoding layers
    for _ in range(3):
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

    # Last-resort unescape
    if ("\\n" in pk or "\\\\" in pk) and not (pk.startswith("-----BEGIN ") and "-----END " in pk):
        try:
            pk = pk.encode("utf-8").decode("unicode_escape")
        except Exception:
            pass

    pk = pk.strip()

    # Find header/footer
    header_match = re.search(r"(-----BEGIN [^\n]+-----)", pk)
    footer_match = re.search(r"(-----END [^\n]+-----)", pk)
    if not header_match or not footer_match:
        raise ValueError("private_key appears malformed (missing PEM header/footer)")

    header = header_match.group(1)
    footer = footer_match.group(1)

    # Extract base64 body between header and footer
    body_match = re.search(r"-----BEGIN [^\n]+-----\s*(.*?)\s*-----END [^\n]+-----", pk, re.S)
    if not body_match:
        raise ValueError("private_key PEM body not found")

    body = body_match.group(1)

    # Remove any characters that are not valid in base64
    body_clean = re.sub(r"[^A-Za-z0-9+/=]", "", body)

    if not body_clean:
        raise ValueError("private_key PEM body empty after cleaning")

    # Re-wrap into 64-character lines
    wrapped = "\n".join([body_clean[i:i+64] for i in range(0, len(body_clean), 64)])

    pk_clean = f"{header}\n{wrapped}\n{footer}\n"

    # Validate by attempting to parse (fails fast with clear error)
    try:
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        from cryptography.hazmat.backends import default_backend
        load_pem_private_key(pk_clean.encode("utf-8"), password=None, backend=default_backend())
    except Exception as e:
        raise ValueError(f"private_key failed PEM parse validation after cleaning: {e}")

    return pk_clean


def get_google_service_account():
    """Return a credentials dict for a Google service account.

    Sources checked (in order):
    - Environment variable GOOGLE_SERVICE_ACCOUNT_JSON (raw or double-encoded JSON)
    - Local files: google_credentials.json, secure_google_credentials.json two levels up

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
        for filename in ["google_credentials.json", "secure_google_credentials.json", "credentials.json"]:
            local_key_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), filename)
            if os.path.exists(local_key_path):
                try:
                    with open(local_key_path, 'r', encoding='utf-8') as f:
                        creds_dict = json.load(f)
                    break
                except Exception:
                    pass
                
    if not creds_dict:
        raise ValueError("Google Service Account credentials not found in environment or local credential files.")

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
