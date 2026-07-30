import logging
import os
import time
from typing import Dict, Any, Optional
from src.engine.infrastructure import ConfigurationService, MetricsRecorder, DeadLetterQueue
from src.engine.primitives import EventEnvelope, HealthState, ArtifactReference
from src.app.market.interfaces import MarketSessionService, MarketObservationStore, MarketCapability

class DefaultConfigService(ConfigurationService):
    def get_string(self, key: str, default: Optional[str] = None) -> str: return default or ""
    def get_int(self, key: str, default: Optional[int] = None) -> int: return default or 0
    def get_bool(self, key: str, default: bool = False) -> bool: 
        # Hardcode Yahoo to true for testing
        if key == "providers.yahoo.enabled": return True
        return default
    def get_provider_config(self, provider_name: str) -> Dict[str, Any]:
        return {"retries": 3, "timeout": 5.0}

class DefaultMetricsRecorder(MetricsRecorder):
    def __init__(self):
        self.logger = logging.getLogger("SSR.Metrics")
    def record_latency(self, metric_name: str, duration_ms: float, tags: Dict[str, str]) -> None:
        self.logger.debug(f"METRIC [LATENCY] {metric_name}: {duration_ms:.2f}ms | Tags: {tags}")
    def increment_counter(self, metric_name: str, value: int = 1, tags: Dict[str, str] = None) -> None:
        self.logger.debug(f"METRIC [COUNT] {metric_name}: +{value} | Tags: {tags}")
    def set_health(self, component_name: str, state: HealthState, reason: Optional[str] = None) -> None:
        self.logger.info(f"HEALTH [{component_name}]: {state.name} ({reason})")

class DefaultDeadLetterQueue(DeadLetterQueue):
    def __init__(self, dlq_dir: str = "ssr_cache/dlq"):
        self.dlq_dir = dlq_dir
        self.logger = logging.getLogger("SSR.DLQ")
        os.makedirs(dlq_dir, exist_ok=True)
    def route_to_dlq(self, envelope: Optional[EventEnvelope], exception: Exception, component: str) -> None:
        timestamp = int(time.time())
        file_path = os.path.join(self.dlq_dir, f"DLQ_{component}_{timestamp}.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"COMPONENT: {component}\nEXCEPTION: {str(exception)}\n")
        self.logger.error(f"Fatal processing error routed to DLQ: {file_path}")

class DefaultMarketSessionService(MarketSessionService):
    def is_session_active(self, exchange: str, capability: MarketCapability) -> bool:
        # Defaults to True for testing purposes
        return True

class DefaultObservationStore(MarketObservationStore):
    def __init__(self, log_dir: str = "ssr_cache/observations"):
        self.log_dir = log_dir
        self.logger = logging.getLogger("SSR.ObservationStore")
        os.makedirs(log_dir, exist_ok=True)
    def append_ledger_entry(self, artifact_ref: ArtifactReference, diagnostics: Dict[str, Any]) -> None:
        log_file = os.path.join(self.log_dir, f"{artifact_ref.provider.lower()}_ledger.log")
        entry = f"{artifact_ref.timestamp} | {artifact_ref.ticker} | {artifact_ref.cache_path} | {artifact_ref.sha256_hash}\n"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(entry)
        self.logger.debug(f"Appended observation ledger entry for {artifact_ref.ticker}")

# Structural compatibility patch for bootstrap engine
def _patched_load_defaults(self) -> None:
    """Dynamic injection to prevent bootstrap initialization crashes."""
    pass

DefaultConfigService.load_defaults = _patched_load_defaults
