import sqlite3
import os
import logging

logger = logging.getLogger(__name__)

DB_PATH = "ssr_observability.db"

def ensure_columns(conn, table, columns):
    """Safely inspect existing table schema via PRAGMA and add missing columns dynamically."""
    try:
        cursor = conn.execute(f"PRAGMA table_info({table})")
        existing = {row[1] for row in cursor.fetchall()}
        for col_name, col_type in columns.items():
            if col_name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type} DEFAULT 0")
                logger.info(f"[DATABASE MIGRATION] Added missing column '{col_name}' to table '{table}'.")
        conn.commit()
    except Exception as e:
        logger.error(f"[DATABASE MIGRATION ERROR] Failed to update schema for {table}: {e}")

def init_db():
    """Ensures all core SQLite database tables and telemetry columns are fully provisioned."""
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    
    # Base table definitions
    conn.execute("""
        CREATE TABLE IF NOT EXISTS workflow_health (
            timestamp TEXT PRIMARY KEY,
            total_scanned INTEGER,
            articles INTEGER,
            errors INTEGER,
            drift_score REAL,
            runtime REAL
        );
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS run_metrics_log (
            timestamp TEXT PRIMARY KEY
        );
    """)
    
    conn.commit()

    # Dynamic schema auto-migration for telemetry attributes
    ensure_columns(conn, "workflow_health", {
        "failed": "INTEGER",
        "succeeded": "INTEGER",
        "skipped": "INTEGER"
    })
    
    conn.close()
    logger.info("[DATABASE] Ready and fully migrated.")


# Alias for compatibility with monitor.py imports
initialise_database = init_db
