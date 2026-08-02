import csv
import sys
import os
from src.validation.db_helpers import initialize_schema, insert_historical_event

def import_from_csv(csv_path):
    if not os.path.exists(csv_path):
        print(f"[VQA ERROR] CSV file not found: {csv_path}")
        sys.exit(1)
    
    # Ensure the standalone database and table exist before importing
    initialize_schema()
    
    # Map expected CSV headers to SQLite column names
    column_mapping = {
        "Date": "date",
        "Company": "company",
        "Ticker": "ticker",
        "Country": "country",
        "Exchange": "exchange",
        "Event Type": "event_type",
        "Announcement URL": "announcement_url",
        "Primary Source": "primary_source",
        "Official Filing": "official_filing",
        "Expected Ontology": "expected_ontology",
        "Expected Rule": "expected_rule",
        "Detected (Y/N)": "detected_yn",
        "Detection Timestamp": "detection_timestamp",
        "Detection Delay": "detection_delay",
        "Reason Missed": "reason_missed",
        "Reviewer Notes": "reviewer_notes"
    }
    
    inserted = 0
    with open(csv_path, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            event_data = {}
            # Safely map columns, defaulting to empty string if a column is missing
            for csv_col, db_col in column_mapping.items():
                event_data[db_col] = row.get(csv_col, "").strip()
                
            insert_historical_event(event_data)
            inserted += 1
            
    print(f"[VQA] Successfully imported {inserted} historical events into validation.db.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m src.validation.import_csv <path_to_csv>")
        sys.exit(1)
        
    csv_file_path = sys.argv[1]
    import_from_csv(csv_file_path)
