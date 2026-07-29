from dataclasses import dataclass
from typing import Dict, List

@dataclass(frozen=True)
class MarketProvenance:
    """Strict tracking metadata required for all canonical market objects."""
    object_id: str
    source: str                 # e.g., "YAHOO", "POLYGON", "IBKR", "REPLAY"
    observed_at: float          # Unix Epoch UTC of framework ingestion
    quote_timestamp: float      # Unix Epoch UTC issued by upstream provider
    dependency_hash: str        # SHA-256 hash of raw input file/payload
    correlation_id: str
    confidence_score: float     # 0.0 to 1.0
    is_replay: bool
    market_status: str          # "OPEN" | "CLOSED" | "HALTED"
    session_type: str           # "REGULAR" | "PRE_MARKET" | "POST_MARKET"
    price_source: str           # "REGULAR_MARKET" | "DELAYED" | "INDICATIVE"
    schema_version: str = "1.0" # Default field placed last

@dataclass(frozen=True)
class OBJ_MKT_PRICE:
    provenance: MarketProvenance
    ticker: str
    price: float
    currency: str
    exchange: str

@dataclass(frozen=True)
class OBJ_MKT_QUOTE:
    provenance: MarketProvenance
    ticker: str
    bid: float
    ask: float
    bid_size: int
    ask_size: int

@dataclass(frozen=True)
class OBJ_MKT_OPTION_CHAIN_HEADER:
    provenance: MarketProvenance
    underlying_ticker: str
    underlying_price: float
    expiration_dates: List[int]
    active_contracts_count: int

@dataclass(frozen=True)
class OBJ_MKT_OPTION_CONTRACT:
    provenance: MarketProvenance
    contract_symbol: str        # e.g., "DSGR260821C00055000"
    underlying_ticker: str
    strike: float
    right: str                  # "CALL" | "PUT"
    expiration_utc: int
    last_price: float
    bid: float
    ask: float
    volume: int
    open_interest: int
    implied_volatility: float
