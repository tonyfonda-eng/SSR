import os
import sys
from google import genai
raw_keys = os.environ.get("GEMINI_API_KEY", "")
api_keys = [k.strip() for k in raw_keys.split(",") if k.strip()]
if not api_keys:
    print("No keys found")
    sys.exit(0)
client = genai.Client(api_key=api_keys[0])
for model in ['gemini-2.0-flash', 'gemini-1.5-flash']:
    print(f"\n--- Testing {model} ---")
    try:
        response = client.models.generate_content(model=model, contents="Hello")
        print("Success:", response.text)
    except Exception as e:
        print("Raw Error:", repr(e))
