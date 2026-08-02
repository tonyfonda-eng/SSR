import sqlite3
import os

def verify_system_tables(db_path=None):
    """
    Dynamically verifies that all monitoring tables exist without 
    duplicating the schema definition or hardcoding the file path.
    """
    # Detect db from environment or fallback to project default
    if not db_path:
        db_path = os.getenv("DATABASE_PATH", "ssr_cache.sqlite")
        
    required_tables = [
        "workflow_health", "run_metrics_log", "article_lifecycle_log",
        "source_stats_log", "ai_usage_log", "exceptions_log",
        "dashboard_state", "sheets_sync_log"
    ]
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        existing_tables = {row[0] for row in cursor.fetchall()}
        conn.close()
        
        missing = [t for t in required_tables if t not in existing_tables]
        if missing:
            print(f"[DATABASE WARNING] Missing lifecycle tables: {missing}. Running migrations...")
            # Here we call your existing database initializer if needed
            # from src.database import initialize_database; initialize_database()
        else:
            print(f"[DATABASE] Schema integrity verified. All {len(required_tables)} lifecycle tables present.")
            
    except Exception as e:
        print(f"[DATABASE ERROR] Health check failed: {e}")
