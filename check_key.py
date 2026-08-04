import hashlib
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.primitives import serialization
from src.config.secrets import get_google_service_account

try:
    creds = get_google_service_account()
    print("client_email:", creds.get("client_email"))
    print("private_key_id:", creds.get("private_key_id"))
    pk = creds.get("private_key", "")
    print("len(private_key) chars:", len(pk))

    key = load_pem_private_key(pk.encode('utf-8'), password=None)
    pub = key.public_key()
    pub_bytes = pub.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    print("[SUCCESS] public key SHA256:", hashlib.sha256(pub_bytes).hexdigest())
except Exception as e:
    print("[ERROR] Failed to load or validate credentials:", e)
