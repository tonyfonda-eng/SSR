from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from src.engine.primitives import EventEnvelope, HealthState

class ConfigurationService(ABC):
    """Central authority for runtime parameters, timeouts, credentials, and feature flags."""
    
    @abstractmethod
    def get_string(self, key: str, default: Optional[str] = None) -> str:
        pass

    @abstractmethod
    def get_int(self, key: str, default: Optional[int] = None) -> int:
        pass

    @abstractmethod
    def get_bool(self, key: str, default: bool = False) -> bool:
        pass

    @abstractmethod
    def get_provider_config(self, provider_name: str) -> Dict[str, Any]:
        """Retrieves a scoped nested dictionary of retry rules, timeouts, and boundaries."""
        pass


class MetricsRecorder(ABC):
    """Abstract interface for recording latency distributions, operational counts, and errors."""
    
    @abstractmethod
    def record_latency(self, metric_name: str, duration_ms: float, tags: Dict[str, str]) -> None:
        pass

    @abstractmethod
    def increment_counter(self, metric_name: str, value: int = 1, tags: Dict[str, str] = None) -> None:
        pass

    @abstractmethod
    def set_health(self, component_name: str, state: HealthState, reason: Optional[str] = None) -> None:
        pass


class DeadLetterQueue(ABC):
    """
    Storage sink for valid payloads that suffered unrecoverable failures during downstream processing
    (e.g., adapter parsing crashes, database lock exhaustion, projection failures).
    """
    
    @abstractmethod
    def route_to_dlq(self, envelope: EventEnvelope, exception: Exception, component: str) -> None:
        """Persists the failed envelope alongside its context trace for offline forensics."""
        pass
