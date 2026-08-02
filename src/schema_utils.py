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
