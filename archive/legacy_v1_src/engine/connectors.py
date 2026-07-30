from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from src.knowledge.schemas.epistemology import CandidateAssertion

class Transport(ABC):
    """Layer 0: Pure network I/O. Handles timeouts, retries, and throttling."""
    @abstractmethod
    def get(self, url: str, params: Optional[Dict[str, Any]] = None) -> str:
        pass

class MarketDataConnector(ABC):
    """Layer 1: Unified vendor-specific path and endpoint routing."""
    def __init__(self, transport: Transport):
        self.transport = transport

    @abstractmethod
    def fetch_market_price(self, ticker: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def fetch_option_chain(self, ticker: str) -> Dict[str, Any]:
        pass

class MarketDataAdapter(ABC):
    """Layer 2: Standardizes vendor payloads directly into CandidateAssertions."""
    @abstractmethod
    def adapt_price_snapshot(self, raw_payload: Dict[str, Any], event_id: str) -> CandidateAssertion:
        pass
        
    @abstractmethod
    def adapt_chain(self, raw_payload: Dict[str, Any], event_id: str) -> List[CandidateAssertion]:
        pass
