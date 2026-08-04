import hashlib
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.primitives import serialization
from src.config.secrets import get_google_service_account

creds = get_google_service_account()
print("client_email:", creds.get("client_email"))
print("private_key_id:", creds.get("private_key_id"))
pk = creds.get("private_key", "")
print("len(private_key) chars:", len(pk))

# parse the PEM and print public-key SHA256 fingerprint (no private key output)
key = load_pem_private_key(pk.encode('utf-8'), password=None)
pub = key.public_key()
pub_bytes = pub.public_bytes(
    encoding=serialization.Encoding.DER,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
)
print("public key SHA256:", hashlib.sha256(pub_bytes).hexdigest())
