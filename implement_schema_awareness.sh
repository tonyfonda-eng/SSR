#!/bin/bash
set -e

echo "📦 Step 1: Navigating to workspace..."
cd ~/special-situations-radar-main

echo "🛠️ Step 2: Creating src/schema_utils.py..."
cat << 'PYTHON_EOF' > src/schema_utils.py
import sqlite3
import logging

logger = logging.getLogger(__name__)

def get_columns(conn, table_name):
    """Inspects database table schema at runtime via PRAGMA table_info."""
    try:
        cursor = conn.execute(f"PRAGMA table_info({table_name});")
        return {row[1] for row in cursor.fetchall()}
    except Exception as e:
        logger.warning(f"[SCHEMA UTILS] Failed to inspect table '{table_name}': {e}")
        return set()

def build_safe_select(conn, table_name, desired_columns):
    """
    Builds a dynamic SELECT query matching only columns that actually exist in the table.
    Returns: (query_string, existing_columns, missing_columns, coverage_ratio)
    """
    available = get_columns(conn, table_name)
    existing = [col for col in desired_columns if col in available]
    missing = [col for col in desired_columns if col not in available]
    
    coverage = len(existing) / len(desired_columns) if desired_columns else 1.0
    
    if not existing:
        # Fallback to SELECT rowid if no desired columns exist
        query = f"SELECT rowid FROM {table_name}"
    else:
        cols_str = ", ".join(existing)
        query = f"SELECT {cols_str} FROM {table_name}"
        
    return query, existing, missing, coverage

def print_schema_audit(conn, tables_spec):
    """Prints the SQLite Schema Audit and logs architecture warnings if coverage < 80%."""
    print("\n" + "=" * 40)
    print("SQLite Schema Audit")
    print("=" * 40)
    
    overall_compliant = True
    audit_report_lines = ["# SQLite Schema Audit Report\n"]
    
    for table_name, desired in tables_spec.items():
        available = get_columns(conn, table_name)
        existing = [c for c in desired if c in available]
        missing = [c for c in desired if c not in available]
        coverage = (len(existing) / len(desired)) * 100 if desired else 100.0
        
        print(f"\n{table_name}")
        audit_report_lines.append(f"## Table: `{table_name}`\n")
        
        for col in desired:
            if col in available:
                print(f"  ✓ {col}")
                audit_report_lines.append(f"- [x] `{col}` (Present)")
            else:
                print(f"  ✗ {col} (Missing)")
                audit_report_lines.append(f"- [ ] `{col}` **(Missing)**")
                
        print(f"Coverage: {len(existing)} / {len(desired)} fields ({coverage:.1f}%)")
        audit_report_lines.append(f"\n**Coverage:** {len(existing)} / {len(desired)} fields (**{coverage:.1f}%**)\n---")
        
        if coverage < 80.0:
            print(f"[ARCHITECTURE WARNING] {table_name} schema is behind expected version ({coverage:.1f}%). Recommended: run migrations.")
            overall_compliant = False

    print("\n" + "=" * 40 + "\n")
    
    # Write audit report to docs/SCHEMA_AUDIT.md
    import os
    os.makedirs("docs", exist_ok=True)
    with open("docs/SCHEMA_AUDIT.md", "w", encoding="utf-8") as f:
        f.write("\n".join(audit_report_lines))
        
    return overall_compliant
PYTHON_EOF

echo "🛠️ Step 3: Updating src/sheets_sync.py to use schema-utils..."
python3 -c "
path = 'src/sheets_sync.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Add schema_utils import if not present
if 'import schema_utils' not in content and 'from src import schema_utils' not in content:
    content = 'from src import schema_utils\nimport sqlite3\n' + content

# Replace brittle raw select queries with schema_utils safe builder
target_snippet = '''def fetch_latest_metrics():'''
if target_snippet in content:
    replacement = '''def fetch_latest_metrics():
    try:
        conn = sqlite3.connect(\"ssr_observability.db\")
        desired = [\"run_id\", \"timestamp\", \"runtime\", \"success\", \"succeeded\", \"failed\", \"skipped\", \"emails\", \"articles\", \"exception\", \"exceptions\", \"error\", \"errors\"]
        
        # Audit schema on first boot
        schema_utils.print_schema_audit(conn, {\"workflow_health\": desired, \"run_metrics_log\": desired})
        
        query, existing, missing, coverage = schema_utils.build_safe_select(conn, \"workflow_health\", desired)
        if missing:
            for m in missing:
                print(f\"[SCHEMA WARNING] workflow_health missing: {m}\")
                
        cursor = conn.cursor()
        cursor.execute(query + \" ORDER BY timestamp DESC LIMIT 1;\")
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return {}
            
        # Map existing columns back to a dict
        res = {}
        for idx, col_name in enumerate(existing):
            res[col_name] = row[idx]
            
        # Provide sensible defaults for missing semantic fields
        for col in desired:
            if col not in res:
                res[col] = None if \"id\" in col or \"timestamp\" in col or \"exception\" in col else 0
                
        return res
    except Exception as e:
        print(f\"[ERROR] Failed to fetch latest run metrics from SQLite: {e}\")
        return {}
'''
    # Find and replace the function body
    import re
    content = re.sub(r'def fetch_latest_metrics\(\).*?(?=\ndef |\Z)', replacement, content, flags=re.DOTALL)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('[OK] Refactored src/sheets_sync.py successfully.')
"

echo "🚀 Step 4: Committing and pushing architectural updates..."
git add src/schema_utils.py src/sheets_sync.py docs/SCHEMA_AUDIT.md
git commit -m "refactor(schema): implement schema-aware querying and runtime audit reporting"
git pull --rebase origin main
git push origin main

echo "✅ Schema-Awareness Sprint completed successfully!"
