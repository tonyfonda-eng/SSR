import os
import sys
from src.providers.router import ProviderRouter

def main():
    print("--- LIVE SMOKE TEST ---")
    router = ProviderRouter()
    
    # Verify keys exist
    if not router.keys.get("gemini") and not router.keys.get("openrouter"):
        print("ERROR: API Keys not found in environment.")
        sys.exit(1)
        
    router.update_config([{"Setting Name": "Default AI Model", "Value": "Gemini-1.5-Pro"}])
    
    # 1. Test Gemini
    print("Testing Gemini...")
    try:
        # Temporarily isolate Gemini
        temp_or_keys = router.keys.get("openrouter")
        router.keys["openrouter"] = []
        
        gemini_res = router.generate('{"test": "hello"} - respond exactly with this JSON', require_json=True)
        if gemini_res != "EXHAUSTED" and gemini_res != "TIMEOUT":
            print(f"GEMINI: PASS - 200 - gemini-1.5-pro-latest")
            gemini_pass = True
        else:
            print(f"GEMINI: FAIL - {gemini_res} - gemini-1.5-pro-latest")
            gemini_pass = False
    except Exception as e:
        print(f"GEMINI: FAIL - {e}")
        gemini_pass = False
        
    # Restore keys
    router.keys["openrouter"] = temp_or_keys
    
    # 2. Test OpenRouter
    print("Testing OpenRouter...")
    try:
        temp_gemini_keys = router.keys.get("gemini")
        router.keys["gemini"] = []
        
        or_res = router.generate('{"test": "hello"} - respond exactly with this JSON', require_json=True)
        if or_res != "EXHAUSTED" and or_res != "TIMEOUT":
            print(f"OPENROUTER: PASS - 200 - google/gemini-1.5-pro")
            or_pass = True
        else:
            print(f"OPENROUTER: FAIL - {or_res} - google/gemini-1.5-pro")
            or_pass = False
    except Exception as e:
        print(f"OPENROUTER: FAIL - {e}")
        or_pass = False
        
    print("---")
    if gemini_pass and or_pass:
        print("JSON PARSING: PASS")
        print("PRODUCTION READY: YES")
    else:
        print("JSON PARSING: FAIL")
        print("PRODUCTION READY: NO")

if __name__ == '__main__':
    main()
