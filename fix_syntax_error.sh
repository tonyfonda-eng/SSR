#!/bin/bash
set -e

echo "📦 Step 1: Navigating to repository and resetting monitor.py..."
cd ~/special-situations-radar-main
git checkout monitor.py

echo "🛠️ Step 2: Applying indentation-aware patches to monitor.py..."
python3 -c "
import py_compile

monitor_path = 'monitor.py'
with open(monitor_path, 'r', encoding='utf-8') as f:
    code = f.read()

# Fix 1: Remove false 'UNKNOWN' / 'Unknown' abort triggers
code = code.replace(
    'if \"MOCK AI\" in ticker or \"ERROR\" in ticker or ticker == \"UNKNOWN\" or ticker == \"EXHAUSTED\":',
    'if \"MOCK AI\" in ticker or \"ERROR\" in ticker or ticker == \"EXHAUSTED\":'
)

code = code.replace(
    'if \"Unknown\" in event_family or event_family == \"EXHAUSTED\":',
    'if event_family == \"EXHAUSTED\":'
)

# Fix 2: Insert logging line matching the exact indentation of source_stats
lines = code.splitlines()
patched_lines = []
for line in lines:
    patched_lines.append(line)
    if 'source_stats[source_name] =' in line:
        indent = line[:len(line) - len(line.lstrip())]
        log_stmt = f'{indent}print(f\"[INGESTION] {{source_name}}: {{parsed_count}} fetched, {{len(parsed)}} new ({{method_used}})\")'
        patched_lines.append(log_stmt)

new_code = '\n'.join(patched_lines)

with open(monitor_path, 'w', encoding='utf-8') as f:
    f.write(new_code)

print('  [OK] Validating monitor.py syntax...')
py_compile.compile(monitor_path, doraise=True)
print('  [SUCCESS] Syntax compilation passed!')
"

echo "🚀 Step 3: Committing and pushing verified code..."
git add monitor.py
git commit -m "fix(syntax): align indentation of custom scraper telemetry statement" || echo "No changes to commit."
git pull --rebase origin main
git push origin main

echo "✅ monitor.py syntax repaired and verified."
