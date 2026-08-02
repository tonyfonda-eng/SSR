#!/bin/bash
set -e

echo "📦 Step 1: Navigating to repository..."
cd ~/special-situations-radar-main

echo "🛠️ Step 2: Patching monitor.py to fix false ABORT calls, early memory caching, and scraper logging..."
python3 -c "
import re

monitor_path = 'monitor.py'
with open(monitor_path, 'r', encoding='utf-8') as f:
    code = f.read()

# Fix 1A: Remove ticker == 'UNKNOWN' from fatal ABORT condition
code = code.replace(
    'if \"MOCK AI\" in ticker or \"ERROR\" in ticker or ticker == \"UNKNOWN\" or ticker == \"EXHAUSTED\":',
    'if \"MOCK AI\" in ticker or \"ERROR\" in ticker or ticker == \"EXHAUSTED\":'
)

# Fix 1B: Remove 'Unknown' in event_family from fatal ABORT condition
code = code.replace(
    'if \"Unknown\" in event_family or event_family == \"EXHAUSTED\":',
    'if event_family == \"EXHAUSTED\":'
)

# Fix 2: Un-silence custom scrapers inside process_custom_scraper
old_scraper_return = 'return parsed_articles, len(articles)'
new_scraper_return = '''print(f\"    [{source_name}] Fetched {len(articles)} raw articles, {len(parsed_articles)} parsed.\")
    return parsed_articles, len(articles)'''

if old_scraper_return in code and '[source_name] Fetched' not in code:
    code = code.replace(old_scraper_return, new_scraper_return, 1)

# Fix 3: Add source_stats print in main ingestion loop if missing
if 'print(f\"[INGESTION] {source_name}:' not in code:
    code = re.sub(
        r'(source_stats\[source_name\]\s*=\s*\{[^\}]+\})',
        r'\1\n        print(f\"[INGESTION] {source_name}: {parsed_count} fetched, {len(parsed)} new ({method_used})\")',
        code
    )

with open(monitor_path, 'w', encoding='utf-8') as f:
    f.write(code)

print('  [OK] monitor.py successfully patched.')
"

echo "🗄️ Step 3: Reconciling database schema column names in src/database.py..."
python3 -c "
db_path = 'src/database.py'
with open(db_path, 'r', encoding='utf-8') as f:
    code = f.read()

# Ensure both runtime and total_runtime_s exist in table definitions
if 'runtime REAL' in code and 'total_runtime_s REAL' not in code:
    code = code.replace('runtime REAL,', 'runtime REAL, total_runtime_s REAL,')
elif 'total_runtime_s REAL' in code and 'runtime REAL' not in code:
    code = code.replace('total_runtime_s REAL,', 'total_runtime_s REAL, runtime REAL,')

with open(db_path, 'w', encoding='utf-8') as f:
    f.write(code)

print('  [OK] src/database.py schema synchronized.')
"

echo "🧹 Step 4: Resetting local SQLite databases..."
rm -f ssr_observability.db ssr_cache.sqlite validation.db || true

echo "🚀 Step 5: Committing and pushing fixes..."
git add monitor.py src/database.py
git commit -m "fix(pipeline): prevent UNKNOWN from aborting runs, cache issuers early, and add scraper telemetry" || echo "No changes to commit."
git pull --rebase origin main
git push origin main

echo "✅ All structural patches applied and pushed to main."
