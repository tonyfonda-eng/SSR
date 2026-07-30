from enum import Enum
from dataclasses import dataclass
from typing import Optional

class AlertLifecycle(Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    SUPPRESSED = "SUPPRESSED"
    EXPIRED = "EXPIRED"

class AlertSeverity(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"

@dataclass
class Alert:
    alert_id: str
    correlation_id: str
    dependency_hash: str
    timestamp: str
    ticker: str
    rule_fired: str
    value: float
    severity: AlertSeverity
    lifecycle_state: AlertLifecycle = AlertLifecycle.OPEN
    retry_count: int = 0
    last_error: Optional[str] = None
