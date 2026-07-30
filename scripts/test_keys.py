import os
from google import genai
import sys

def main():
    print("=== Google AI API Key Tester ===")
    raw_keys = os.environ.get("GEMINI_API_KEY", "")
    api_keys = [k.strip() for k in raw_keys.split(",") if k.strip()]

    for i in range(1, 11):
        val = os.environ.get(f"GEMINI_API_KEY_{i}")
        if val:
            keys = [k.strip() for k in val.split(",") if k.strip()]
            api_keys.extend(keys)

    api_keys = list(set(api_keys))
    
    if not api_keys:
        print("[ERROR] No GEMINI_API_KEY environment variables found.")
        sys.exit(1)

    print(f"Found {len(api_keys)} unique API keys to test.\n")

    print(f"\n--- Available Models for Key 1 ---")
    try:
        client = genai.Client(api_key=api_keys[0])
        for model in client.models.list():
            if 'flash' in model.name:
                print(f"- {model.name}")
    except Exception as e:
        print(f"Error fetching models: {e}")
        
    sys.exit(0)

    print(f"\n=== Summary ===")
    print(f"Working keys: {success_count} / {len(api_keys)}")
    if success_count == 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
