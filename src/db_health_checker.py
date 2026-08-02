import sqlite3
from src.config import SYSTEM_SETTINGS
from src.database import EXPECTED_TABLES

def verify_system_tables():
    """
    Dynamically verifies tables using a single source of truth.
    """
    db_path = SYSTEM_SETTINGS.get("DATABASE_PATH", "ssr_cache.sqlite")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        existing_tables = {row[0] for row in cursor.fetchall()}
        conn.close()
        
        missing = [t for t in EXPECTED_TABLES if t not in existing_tables]
        if missing:
            print(f"[DATABASE WARNING] Missing tables: {missing}. Migrations required.")
        else:
            print(f"[DATABASE] Schema integrity verified. {len(EXPECTED_TABLES)} tables present.")
            
    except Exception as e:
        print(f"[DATABASE ERROR] Health check failed: {e}")
