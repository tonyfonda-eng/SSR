import os

print("--- RUNTIME ENVIRONMENT VARIABLES ---")
keys_of_interest = [k for k in os.environ.keys() if any(x in k.upper() for x in ['SMTP', 'GMAIL', 'EMAIL', 'MAIL', 'ALERT'])]

for k in keys_of_interest:
    val = os.environ.get(k, "")
    exists = "YES" if val else "NO"
    length = len(val)
    masked = (val[:3] + "*" * (length - 3)) if length > 3 else ("*" * length)
    print(f"{k} = {masked}")
    print(f"exists = {exists}")
    print(f"length = {length}\n")

print("--- RECIPIENT TRACE ---")
print(f"ALERT_EMAIL_RECIPIENT = {os.environ.get('ALERT_EMAIL_RECIPIENT')}")
