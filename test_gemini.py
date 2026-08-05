import os
import requests

api_key = os.environ.get("GEMINI_API_KEY", "")
if not api_key:
    print("No API key")
else:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": "Hello"}]}]
    }
    r = requests.post(url, headers=headers, json=payload)
    print(r.status_code)
