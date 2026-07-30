import hashlib

def generate_id(prefix: str, unique_string: str) -> str:
    # We added ANNC and ACTION to the whitelist to support the new hierarchy
    allowed_prefixes = {"ANNC", "ACTION", "EVENT", "CASE"}
    
    prefix = prefix.upper()
    if prefix not in allowed_prefixes:
        raise ValueError(f"Invalid prefix: {prefix}. Allowed: {allowed_prefixes}")
    
    # Create a deterministic 8-character hash
    hash_object = hashlib.md5(unique_string.encode('utf-8'))
    short_hash = hash_object.hexdigest()[:8].upper()
    
    return f"{prefix}-{short_hash}"
