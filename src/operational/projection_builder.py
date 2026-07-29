import logging
from datetime import datetime

class ProjectionBuilder:
    """Listens to EventBus domain events and flushes normalized view-states to SQLite."""
    
    def __init__(self, projection_store):
        self.store = projection_store
        self.logger = logging.getLogger("SSR.ProjectionBuilder")

    def handle_sec_filing(self, event_type: str, payload: dict):
        """Transforms raw SEC discovery events into human-readable log rows."""
        accession = payload["accession_number"]
        
        row_data = {
            "Accession_Number": accession,
            "Filing_Title": payload["title"],
            "Cached_Path": payload["cached_path"],
            "Ingested_At": datetime.now().isoformat(),
            "Status": "PROCESSED"
        }
        
        self.store.apply_event(
            sheet_name="01_SEC_Ingestion_Log",
            row_id=accession,
            payload_dict=row_data
        )

    def handle_risk_calculation(self, event_type: str, payload: any):
        """Transforms complex structural mathematical calculations into cockpit layout rows."""
        # Standardizing object attributes vs dict lookups from the bus structure
        ticker = getattr(payload, "ticker", "UNKNOWN")
        correlation_id = getattr(payload, "correlation_id", "N/A")
        result_value = getattr(payload, "result_value", 0.0)
        
        row_data = {
            "Ticker": ticker,
            "Metric": "ASSIGNMENT_RISK",
            "Value": round(result_value, 4),
            "Trigger_Status": "BREACHED" if result_value >= 0.90 else "NOMINAL",
            "Correlation_ID": correlation_id,
            "Last_Calculated": datetime.now().isoformat()
        }
        
        self.store.apply_event(
            sheet_name="02_Risk_Monitor",
            row_id=f"{ticker}_ASSIGNMENT",
            payload_dict=row_data
        )
