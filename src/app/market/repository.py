import logging
import threading
from typing import Dict, Any, Optional
from src.engine.primitives import MutationResult, MutationStatus
from src.app.market.interfaces import MarketStateWriter, MarketStateReader, EqualityPolicy

class MarketRepository(MarketStateWriter, MarketStateReader):
    """
    Pure CQRS state machine. Evaluates observations against current state
    using injected equality policies. Emits zero side-effects.
    """
    
    def __init__(self):
        self.logger = logging.getLogger("SSR.MarketRepository")
        self._lock = threading.Lock()
        self._state: Dict[str, Dict[str, Any]] = {"PRICE": {}, "OPTION_CONTRACT": {}}
        self._policies: Dict[str, EqualityPolicy] = {}

    def register_equality_policy(self, data_type: str, policy: EqualityPolicy) -> None:
        self._policies[data_type.upper()] = policy

    def apply_observation(self, observation: Any) -> MutationResult:
        data_type = getattr(observation, "data_type", None)
        ticker = getattr(observation, "ticker", None)
        payload = getattr(observation, "payload", None)

        if not data_type or not ticker or not payload:
            self.logger.error("Repository rejected observation: Missing routing keys.")
            return MutationResult("1.0", MutationStatus.REJECTED, None, None)

        policy = self._policies.get(data_type)
        if not policy:
            self.logger.warning(f"No equality policy registered for {data_type}.")
            return MutationResult("1.0", MutationStatus.REJECTED, None, None)

        with self._lock:
            prev_state = self._state[data_type].get(ticker)
            is_equal = policy.are_equal(prev_state, payload)

            if not is_equal:
                self._state[data_type][ticker] = payload
                self.logger.info(f"State Mutated: {data_type} for {ticker}")
                return MutationResult("1.0", MutationStatus.UPDATED, prev_state, payload)
            
            return MutationResult("1.0", MutationStatus.UNCHANGED, prev_state, payload)

    def get_latest_price(self, ticker: str) -> Optional[Any]:
        with self._lock:
            return self._state["PRICE"].get(ticker)
