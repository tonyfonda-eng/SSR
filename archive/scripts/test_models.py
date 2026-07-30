import os
from google import genai
raw_keys = os.environ.get("GEMINI_API_KEY", "")
api_keys = [k.strip() for k in raw_keys.split(",") if k.strip()]
if api_keys:
    client = genai.Client(api_key=api_keys[0])
    for m in client.models.list():
        if 'flash' in m.name:
            print(m.name)
