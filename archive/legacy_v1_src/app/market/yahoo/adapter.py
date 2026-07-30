import json
import uuid
import time
from typing import Dict, Any
from src.app.market.interfaces import MarketAdapter
from src.app.market.objects import MarketProvenance, OBJ_MKT_PRICE
from src.engine.primitives import EventEnvelope, EventMetadata, EventTopic

class YahooMarketAdapter(MarketAdapter):
    """
    Pure transformation boundary. Retrieves the payload via the ArtifactReference 
    Claim Check and translates it to canonical domain models.
    """
    
    def __init__(self, event_bus, document_store):
        self.event_bus = event_bus
        self.document_store = document_store

    def handle_raw(self, envelope: EventEnvelope) -> None:
        payload_data = envelope.payload
        artifact_ref = payload_data.get("artifact_reference")
        
        if not artifact_ref or artifact_ref.provider != "YAHOO":
            return

        # Fulfill the Claim Check by retrieving the immutable payload from disk
        raw_payload = self.document_store.read_payload(artifact_ref.cache_path)
        
        parsed = json.loads(raw_payload)
        result = parsed["chart"]["result"][0]
        meta = result["meta"]
        ticker = meta["symbol"]
        
        market_state = meta.get("marketState", "REGULAR").upper()
        
        provenance = MarketProvenance(
            object_id=envelope.metadata.event_id,
            source="YAHOO",
            observed_at=artifact_ref.timestamp,
            quote_timestamp=float(meta["regularMarketTime"]),
            dependency_hash=artifact_ref.sha256_hash,
            correlation_id=envelope.metadata.correlation_id,
            confidence_score=1.0,
            is_replay=envelope.metadata.is_replay,
            market_status="OPEN" if market_state != "CLOSED" else "CLOSED",
            session_type="REGULAR" if market_state == "REGULAR" else "PRE_POST_MARKET",
            price_source="REGULAR_MARKET"
        )
        
        canonical_price = OBJ_MKT_PRICE(
            provenance=provenance,
            ticker=ticker,
            price=float(meta["regularMarketPrice"]),
            currency=meta.get("currency", "USD"),
            exchange=meta.get("exchangeName", "UNKNOWN")
        )

        obs_metadata = EventMetadata(
            topic=EventTopic.OBS_MKT_SNAPSHOT,
            schema_version="1.0",
            correlation_id=envelope.metadata.correlation_id,
            causation_id=envelope.metadata.event_id,
            is_replay=envelope.metadata.is_replay
        )

        obs_envelope = EventEnvelope(
            metadata=obs_metadata,
            payload={
                "data_type": "PRICE",
                "ticker": ticker,
                "payload": canonical_price
            }
        )
        
        self.event_bus.publish(EventTopic.OBS_MKT_SNAPSHOT, obs_envelope)
