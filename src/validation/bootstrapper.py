import sqlite3
import os
from src.config import SYSTEM_SETTINGS

def initialize_validation_db(val_db_path="validation.db"):
    """
    Initializes a decoupled validation tracking database.
    Stores historical accuracy metrics, statistical drift snapshots, and regression bounds.
    """
    conn = sqlite3.connect(val_db_path)
    cursor = conn.cursor()
    
    # 1. Historical Data Log
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historical_runs_summary (
            run_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            total_downloaded INTEGER,
            precision_score REAL,
            recall_score REAL,
            f1_score REAL,
            unaccounted_variance INTEGER
        );
    """)
    
    # 2. Regression Tracking (Golden Dataset Validation Runs)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS regression_test_logs (
            test_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            golden_set_version TEXT,
            expected_alerts INTEGER,
            detected_alerts INTEGER,
            missed_alerts INTEGER,
            silent_failures INTEGER,
            status TEXT
        );
    """)
    
    conn.commit()
    conn.close()
    print(f"[VQA] Validation Database successfully initialized at: {val_db_path}")

if __name__ == "__main__":
    initialize_validation_db()
