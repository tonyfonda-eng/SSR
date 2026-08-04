import json
import os
import ast
import re

def _sanitize_private_key(raw_pk: str) -> str:
    """Normalize and repair a possibly-escaped or corrupted PEM private key.

    - Unwraps common escape/quoting layers.
    - Cleans the base64 body of any non-base64 characters (including stray backslashes).
    - Rewraps base64 into 64-char lines and reconstructs a canonical PEM.
    - Validates with cryptography to fail fast if irreparable.
    """
    if isinstance(raw_pk, bytes):
        pk = raw_pk.decode("utf-8", "strict")
    else:
        pk = str(raw_pk)

    pk = pk.strip()
    if (pk.startswith('"') and pk.endswith('"')) or (pk.startswith("'") and pk.endswith("'")):
        pk = pk[1:-1]

    # Unwrap possible JSON/python quoting and collapse escaped newlines
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

    # Extract header/footer and the body between them
    header_match = re.search(r"(-----BEGIN [^\n]+-----)", pk)
    footer_match = re.search(r"(-----END [^\n]+-----)", pk)
    if not header_match or not footer_match:
        raise ValueError("private_key appears malformed (missing PEM header/footer)")

    header = header_match.group(1)
    footer = footer_match.group(1)

    body_match = re.search(r"-----BEGIN [^\n]+-----\s*(.*?)\s*-----END [^\n]+-----", pk, re.S)
    if not body_match:
        raise ValueError("private_key PEM body not found")

    body = body_match.group(1)

    # Remove any characters that are not valid in base64
    body_clean = re.sub(r"[^A-Za-z0-9+/=]", "", body)
    if not body_clean:
        raise ValueError("private_key PEM body empty after cleaning")

    # Re-wrap into 64-character lines (standard PEM formatting)
    wrapped = "\n".join([body_clean[i:i+64] for i in range(0, len(body_clean), 64)])
    pk_clean = f"{header}\n{wrapped}\n{footer}\n"

    # Validate by attempting to parse it
    try:
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        from cryptography.hazmat.backends import default_backend
        load_pem_private_key(pk_clean.encode("utf-8"), password=None, backend=default_backend())
    except Exception as e:
        raise ValueError(f"private_key failed PEM parse validation after cleaning: {e}")

    return pk_clean