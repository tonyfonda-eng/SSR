import json
import collections

try:
    with open('docs/screening_log.json', 'r') as f:
        screen_log = json.load(f)
    print(f"Total screened items: {len(screen_log)}")
    titles = collections.Counter([item.get('title', 'NO_TITLE') for item in screen_log])
    print(f"Top titles: {titles.most_common(10)}")
    
    reasons = collections.Counter([item.get('drop_reason', 'NONE') for item in screen_log])
    print(f"Drop reasons: {reasons.most_common(10)}")

    hashes = collections.Counter([item.get('article_hash', 'NO_HASH') for item in screen_log])
    print(f"Unique hashes count: {len(hashes)}")
    print(f"Top hashes: {hashes.most_common(10)}")
except Exception as e:
    print(f"Error reading screening_log.json: {e}")

try:
    with open('docs/ingestion_ledger.json', 'r') as f:
        ingest_ledger = json.load(f)
    
    titles_ledger = collections.Counter([item.get('title', 'NO_TITLE') for item in ingest_ledger])
    print(f"Top ledger titles: {titles_ledger.most_common(10)}")
    
    hashes_ledger = collections.Counter([item.get('article_hash', 'NO_HASH') for item in ingest_ledger])
    print(f"Ledger unique hashes: {len(hashes_ledger)}")
    print(f"Ledger top hashes: {hashes_ledger.most_common(10)}")
except Exception as e:
    print(f"Error reading ingestion_ledger.json: {e}")
