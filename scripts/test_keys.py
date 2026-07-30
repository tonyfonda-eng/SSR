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

    print(f"\n--- Testing Active Model ---")
    
    success_count = 0
    for idx, key in enumerate(api_keys):
        masked_key = key[:4] + "*" * (len(key) - 8) + key[-4:] if len(key) > 8 else "***"
        print(f"\nTesting Key {idx+1}/{len(api_keys)} ({masked_key})...")
        
        try:
            client = genai.Client(api_key=key)
            response = client.models.generate_content(
                model="gemini-flash-latest",
                contents="Reply with exactly the word OK"
            )
            text = response.text.strip()
            print(f"  -> SUCCESS! Response: {text}")
            success_count += 1
        except Exception as e:
            error_str = str(e)
            print(f"  -> RAW ERROR: {repr(e)}")

    print(f"\n=== Summary ===")
    print(f"Working keys: {success_count} / {len(api_keys)}")
    if success_count == 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
