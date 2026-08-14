import json
from collections import Counter

try:
    with open('docs/screening_log.json', 'r') as f:
        screen_log = json.load(f)
    
    # Filter for today: 2026-08-14
    today_articles = [item for item in screen_log if '2026-08-14' in item.get('timestamp', '')]
    
    # "New" articles are those that passed the dedupe_hash stage
    new_articles = [item for item in today_articles if item.get('drop_reason') != 'dropped_hash_duplicate']
    
    print(f"Total raw items polled today (including duplicates): {len(today_articles)}")
    print(f"Total NEW articles processed today (passed dedupe): {len(new_articles)}")
    
    if new_articles:
        stages = Counter([item.get('final_stage') for item in new_articles])
        print("\nBreakdown of where new articles ended up:")
        for stage, count in stages.most_common():
            print(f"  - {stage}: {count}")

except Exception as e:
    print(f"Error: {e}")
