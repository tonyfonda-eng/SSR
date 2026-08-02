import sqlite3
import os

# Completely isolated from production settings
VALIDATION_DB_PATH = "validation.db"

def get_validation_connection():
    """Returns a connection to the isolated validation database."""
    return sqlite3.connect(VALIDATION_DB_PATH)

def initialize_schema():
    """Creates the historical_events table if it does not exist."""
    conn = get_validation_connection()
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

def insert_historical_event(event_data):
    """Inserts a single event dictionary into the historical_events table."""
    conn = get_validation_connection()
    cursor = conn.cursor()
    
    columns = ", ".join(event_data.keys())
    placeholders = ", ".join(["?"] * len(event_data))
    query = f"INSERT INTO historical_events ({columns}) VALUES ({placeholders})"
    
    cursor.execute(query, tuple(event_data.values()))
    conn.commit()
    conn.close()
