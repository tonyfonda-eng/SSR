import sqlite3
import os

VALIDATION_DB_PATH = "validation.db"

def initialize_validation_db(val_db_path=VALIDATION_DB_PATH):
    """Initializes the historical tracking tables in the validation DB."""
    conn = sqlite3.connect(val_db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historical_runs_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            total_downloaded INTEGER,
            precision_score REAL,
            recall_score REAL,
            f1_score REAL,
            unaccounted_variance INTEGER
        );
    """)
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

def initialize_historical_events_table(val_db_path=VALIDATION_DB_PATH):
    """Creates the historical_events table matching VQA strict taxonomy."""
    conn = sqlite3.connect(val_db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historical_events (
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
            detection_delay TEXT,
            reason_missed TEXT,
            reviewer_notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()
    print(f"[VQA] Validation Database initialized successfully at: {val_db_path}")

if __name__ == "__main__":
    initialize_validation_db()
    initialize_historical_events_table()
