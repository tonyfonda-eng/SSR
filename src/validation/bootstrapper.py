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

def initialize_golden_dataset_table(val_db_path="validation.db"):
    """
    Creates the regression framework table within validation.db.
    Stores hand-curated special situations to verify against code updates.
    """
    conn = sqlite3.connect(val_db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS golden_backlog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            company TEXT,
            ticker TEXT,
            country TEXT,
            exchange TEXT,
            event_type TEXT,
            announcement_url TEXT,
            primary_source TEXT,
            official_filing TEXT,
            expected_ontology TEXT,
            expected_rule TEXT,
            detected_yn TEXT,
            detection_timestamp TEXT,
            detection_delay_seconds INTEGER,
            reason_missed TEXT,
            reviewer_notes TEXT,
            test_run_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()
    print("[VQA] Golden Backlog validation table successfully injected.")

if __name__ == "__main__":
    initialize_validation_db()
    initialize_golden_dataset_table()
