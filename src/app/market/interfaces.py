from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Set, List
from enum import Enum, auto
from dataclasses import dataclass
from src.engine.primitives import EventEnvelope, TransportResult, MutationResult, ValidationResult

class MarketCapability(Enum):
    PRICE_SNAPSHOT = auto()
    ORDER_BOOK_QUOTE = auto()
    OPTION_CHAIN = auto()
    GREEKS = auto()
    DIVIDENDS = auto()

class ProviderDescriptor:
    def __init__(self, name: str, capabilities: Set[MarketCapability]):
        self.name = name.upper()
        self.capabilities = capabilities

    def supports(self, capability: MarketCapability) -> bool:
        return capability in self.capabilities

class MarketSessionService(ABC):
    @abstractmethod
    def is_session_active(self, exchange: str, capability: MarketCapability) -> bool:
        pass

class MarketDataPoller(ABC):
    @abstractmethod
    def execute(self, ticker: str, capability: MarketCapability, force: bool = False) -> None:
        pass

class MarketPayloadValidator(ABC):
    @abstractmethod
    def validate(self, transport_result: TransportResult) -> ValidationResult:
        pass

class MarketAdapter(ABC):
    @abstractmethod
    def handle_raw(self, envelope: EventEnvelope) -> None:
        pass

class MarketObservationStore(ABC):
    @abstractmethod
    def append_ledger_entry(self, artifact_ref: Any, diagnostics: Dict[str, Any]) -> None:
        pass

class MarketStateWriter(ABC):
    @abstractmethod
    def apply_observation(self, observation: Any) -> MutationResult:
        pass

class MarketStateReader(ABC):
    @abstractmethod
    def get_latest_price(self, ticker: str) -> Optional[Any]:
        pass

class EqualityPolicy(ABC):
    @abstractmethod
    def are_equal(self, current: Any, incoming: Any) -> bool:
        pass

@dataclass
class ProviderBundle:
    descriptor: ProviderDescriptor
    transport_policy: Any
    payload_validator: MarketPayloadValidator
    adapter: MarketAdapter
    pollers: List[MarketDataPoller]

class ProviderRegistry(ABC):
    @abstractmethod
    def register_bundle(self, bundle: ProviderBundle) -> None:
        pass
    
    @abstractmethod
    def resolve_pollers(self, capability: MarketCapability) -> List[MarketDataPoller]:
        pass
