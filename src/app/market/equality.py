from abc import ABC, abstractmethod
from typing import Any
from src.app.market.objects import OBJ_MKT_PRICE, OBJ_MKT_OPTION_CONTRACT

class EqualityPolicy(ABC):
    """Strategy interface for determining if two domain objects represent a state mutation."""
    @abstractmethod
    def are_equal(self, current: Any, incoming: Any) -> bool:
        pass

class PriceEqualityPolicy(EqualityPolicy):
    def are_equal(self, current: OBJ_MKT_PRICE, incoming: OBJ_MKT_PRICE) -> bool:
        if not current: return False
        return (
            current.price == incoming.price and
            current.currency == incoming.currency and
            current.provenance.market_status == incoming.provenance.market_status
        )

class OptionContractEqualityPolicy(EqualityPolicy):
    def are_equal(self, current: OBJ_MKT_OPTION_CONTRACT, incoming: OBJ_MKT_OPTION_CONTRACT) -> bool:
        if not current: return False
        return (
            current.last_price == incoming.last_price and
            current.bid == incoming.bid and
            current.ask == incoming.ask and
            current.open_interest == incoming.open_interest and
            current.implied_volatility == incoming.implied_volatility
        )
