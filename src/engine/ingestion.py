from typing import Dict, Any, List
from src.engine.connectors import MarketDataConnector, MarketDataAdapter
from src.engine.core import SchemaValidator
from src.engine.runtime import ExecutionContext
from src.engine.adapters.sec import SECEDGARConnector, SECEDGARAdapter

class MarketIngestionService:
    def __init__(self, connector: MarketDataConnector, adapter: MarketDataAdapter, validator: SchemaValidator):
        self.connector = connector
        self.adapter = adapter
        self.validator = validator

    def ingest_price(self, ctx: ExecutionContext, ticker: str) -> bool:
        try:
            raw = self.connector.fetch_market_price(ticker)
            candidate = self.adapter.adapt_price_snapshot(raw, ctx.event_id)
            return self._validate_and_publish(ctx, candidate)
        except Exception: return False

    def ingest_option_chain(self, ctx: ExecutionContext, ticker: str) -> int:
        count = 0
        try:
            raw = self.connector.fetch_option_chain(ticker)
            for c in self.adapter.adapt_chain(raw, ctx.event_id):
                if self._validate_and_publish(ctx, c, f"OBJ.OPT.CONTRACT.{c.value_payload['occ_symbol']}"): 
                    count += 1
            return count
        except Exception: return 0

    def ingest_sec_filings(self, ctx: ExecutionContext, sec_connector: SECEDGARConnector, sec_adapter: SECEDGARAdapter, ticker: str, form_type: str = "8-K") -> int:
        ctx.store.record(f"SEC_EDGAR_POLL_REQUESTED: {ticker} ({form_type})")
        count = 0
        try:
            raw_xml = sec_connector.fetch_recent_filings(ticker, form_type)
            candidates = sec_adapter.adapt_filings(raw_xml, ticker, ctx.event_id)
            
            for c in candidates:
                if self._validate_and_publish(ctx, c, c.object_id):
                    count += 1
            
            ctx.store.record(f"SEC_EDGAR_POLL_COMPLETE: Discovered {count} recent {form_type} filings.")
            return count
        except Exception as e:
            ctx.store.record(f"SEC_EDGAR_POLL_FAILED: {ticker} -> {e}")
            return 0

    def _validate_and_publish(self, ctx: ExecutionContext, candidate, override_key: str = None) -> bool:
        cdict = {
            "candidate_id": candidate.candidate_id, "event_id": candidate.event_id,
            "schema_id": candidate.schema_id, "object_id": candidate.object_id,
            "value_payload": candidate.value_payload
        }
        is_valid, _ = self.validator.validate_candidate(cdict)
        if is_valid:
            key = override_key or candidate.object_id
            # Pushing directly to the EventBus instead of silent dict updates
            ctx.bus.publish(key, candidate.value_payload)
            return True
        return False
