import threading
from datetime import datetime
from typing import Dict, Any

class HealthService:
    """Thread-safe telemetry registry for active background connectors and queues."""
    
    def __init__(self, projection_store):
        self.store = projection_store
        self.lock = threading.Lock()
        self.metrics: Dict[str, Dict[str, Any]] = {}

    def report_success(self, subsystem: str, latency_ms: float = 0.0, payload_size: int = 0):
        """Records a successful operational frame for a specific worker."""
        with self.lock:
            if subsystem not in self.metrics:
                self._init_subsystem(subsystem)
            
            stats = self.metrics[subsystem]
            stats["Status"] = "HEALTHY"
            stats["Last_Success"] = datetime.now().isoformat()
            stats["Avg_Latency_ms"] = round((stats["Avg_Latency_ms"] * 4 + latency_ms) / 5, 2)
            
            self._flush_to_projection(subsystem)

    def report_failure(self, subsystem: str, error_msg: str):
        """Logs a fault, increments retry states, and flags warning alerts."""
        with self.lock:
            if subsystem not in self.metrics:
                self._init_subsystem(subsystem)
                
            stats = self.metrics[subsystem]
            stats["Status"] = "DEGRADED"
            stats["Last_Failure"] = datetime.now().isoformat()
            stats["Retries"] += 1
            
            self._flush_to_projection(subsystem)

    def increment_quarantine(self, subsystem: str):
        """Tracks structural schema drift drift anomalies."""
        with self.lock:
            if subsystem not in self.metrics:
                self._init_subsystem(subsystem)
            self.metrics[subsystem]["Quarantine_Count"] += 1
            self._flush_to_projection(subsystem)

    def _init_subsystem(self, subsystem: str):
        self.metrics[subsystem] = {
            "Subsystem": subsystem,
            "Status": "INITIALIZING",
            "Last_Success": "NEVER",
            "Last_Failure": "NEVER",
            "Retries": 0,
            "Circuit_State": "CLOSED",
            "Quarantine_Count": 0,
            "Avg_Latency_ms": 0.0
        }

    def _flush_to_projection(self, subsystem: str):
        """Pushes the telemetry metrics structure direct to the SQLite cache view layer."""
        self.store.apply_event(
            sheet_name="09_Runtime_Status",
            row_id=subsystem,
            payload_dict=self.metrics[subsystem]
        )
