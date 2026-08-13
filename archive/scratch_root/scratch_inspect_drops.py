import json

try:
    with open("docs/screening_log.json", "r") as f:
        data = json.load(f)
    
    count = 0
    for entry in data:
        reason = str(entry.get("drop_reason", ""))
        if reason.startswith("dropped_ontology_score: 0.00"):
            print(f"Article: {entry.get('headline')}")
            print(f"Source: {entry.get('source')}")
            print(f"Reason: {reason}")
            print(f"URL: {entry.get('url')}")
            print("---------------------------------")
            count += 1
            if count >= 5:
                break
                
except Exception as e:
    print(f"Error: {e}")
