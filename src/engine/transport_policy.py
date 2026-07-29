from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional

@dataclass(frozen=True)
class TransportResult:
    """Framework-neutral response bridging network and file I/O protocols."""
    success: bool
    payload: str
    metadata: Dict[str, Any]       # e.g., source, provider_version, cache_path
    diagnostics: Dict[str, Any]    # e.g., elapsed_ms, retries_used, protocol_status

class TransportPolicy(ABC):
    """Abstract policy isolating provider-specific network or authentication mechanics."""
    
    @abstractmethod
    def prepare_session(self, session_context: Any) -> Any:
        """Configures connection states (e.g., token negotiation, handshake)."""
        pass

    @abstractmethod
    def before_request(self, target: str, parameters: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        """Injects authentication or routing modifications prior to execution."""
        pass

    @abstractmethod
    def after_response(self, raw_response: Any) -> TransportResult:
        """Translates protocol-specific responses into a neutral TransportResult."""
        pass

    @abstractmethod
    def recover(self, exception: Exception, attempt: int, config: Dict[str, Any]) -> bool:
        """Evaluates retry logic based on injected operational configuration."""
        pass
