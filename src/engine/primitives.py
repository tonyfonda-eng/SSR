import uuid
import time
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Generic, TypeVar, Dict, Any, Optional

T = TypeVar('T')

# ==========================================
# System Topologies & States
# ==========================================
class EventTopic(Enum):
    RAW_SEC_FILING_STORED = "RAW.SEC.FILING_STORED"
    RAW_MARKET_INGESTED = "RAW.MARKET.INGESTED"
    OBS_MKT_SNAPSHOT = "OBS.MKT.SNAPSHOT"
    OBJ_MKT_UPDATED = "OBJ.MKT.UPDATED"
    OBJ_MKT_UNCHANGED = "OBJ.MKT.UNCHANGED"
    CALC_RISK_ASSIGNMENT = "CALC.RISK.ASSIGNMENT"
    TELEMETRY_METRICS = "TELEMETRY.METRICS"
    SYS_DLQ_ROUTED = "SYS.DLQ.ROUTED"

class HealthState(Enum):
    UNKNOWN = auto()
    STARTING = auto()
    HEALTHY = auto()
    DEGRADED = auto()
    FAILED = auto()

class ValidationSeverity(Enum):
    NONE = auto()
    WARNING = auto()
    CRITICAL = auto()

class MutationStatus(Enum):
    UPDATED = auto()
    UNCHANGED = auto()
    REJECTED = auto()

# ==========================================
# Immutable Data Transfer Objects (DTOs)
# ==========================================
@dataclass(frozen=True)
class ValidationResult:
    schema_version: str
    is_valid: bool
    reason: str
    severity: ValidationSeverity
    provider: str

@dataclass(frozen=True)
class TransportResult:
    schema_version: str
    success: bool
    payload: str
    provider: str
    endpoint: str
    received_at: float
    diagnostics: Dict[str, Any]

@dataclass(frozen=True)
class ArtifactReference:
    schema_version: str
    provider: str
    data_type: str
    ticker: str
    cache_path: str
    sha256_hash: str
    timestamp: float
    size_bytes: int

@dataclass(frozen=True)
class MutationResult:
    schema_version: str
    status: MutationStatus
    previous_state: Optional[Any]
    current_state: Optional[Any]

# ==========================================
# The Generic Event Envelope
# ==========================================
@dataclass(frozen=True)
class EventMetadata:
    schema_version: str
    topic: EventTopic
    correlation_id: str
    causation_id: Optional[str] = None
    is_replay: bool = False
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)

@dataclass(frozen=True)
class EventEnvelope(Generic[T]):
    metadata: EventMetadata
    payload: T
