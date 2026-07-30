import time
import logging
from typing import Optional
from src.app.market.interfaces import MarketDataPoller, MarketCapability, MarketSessionService, MarketPayloadValidator, MarketObservationStore
from src.engine.transport_policy import TransportPolicy
from src.engine.infrastructure import ConfigurationService, MetricsRecorder, DeadLetterQueue
from src.engine.primitives import EventTopic, EventEnvelope, EventMetadata, ArtifactReference

class YahooPriceSnapshotPoller(MarketDataPoller):
    """
    Pure orchestrator for Yahoo Finance price snapshots. 
    Contains zero JSON parsing or business logic.
    """
    
    def __init__(self, 
                 config: ConfigurationService,
                 session_service: MarketSessionService,
                 transport_client: Any, 
                 transport_policy: TransportPolicy,
                 validator: MarketPayloadValidator,
                 document_store: Any,
                 observation_store: MarketObservationStore,
                 event_bus: Any,
                 metrics: MetricsRecorder,
                 dlq: DeadLetterQueue):
                 
        self.config = config
        self.session_service = session_service
        self.transport_client = transport_client
        self.transport_policy = transport_policy
        self.validator = validator
        self.document_store = document_store
        self.observation_store = observation_store
        self.event_bus = event_bus
        self.metrics = metrics
        self.dlq = dlq
        self.logger = logging.getLogger("SSR.YahooPoller")

    def execute(self, ticker: str, capability: MarketCapability, force: bool = False) -> None:
        if capability != MarketCapability.PRICE_SNAPSHOT:
            return

        # 1. Configuration & Session Gates
        if not self.config.get_bool("providers.yahoo.enabled", default=True):
            return
            
        if not force and not self.session_service.is_session_active("NYSE", capability):
            self.metrics.increment_counter("poller.skipped.market_closed", tags={"provider": "YAHOO"})
            return

        start_time = time.time()
        
        # 2. Invoke Transport Layer
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1m&range=1d"
        try:
            # The client handles the execution loop using the injected YahooTransportPolicy
            transport_result = self.transport_client.execute_with_policy(url, self.transport_policy)
        except Exception as e:
            self.metrics.increment_counter("poller.transport_failure", tags={"provider": "YAHOO"})
            self.dlq.route_to_dlq(envelope=None, exception=e, component="YahooPriceSnapshotPoller")
            return
            
        self.metrics.record_latency("poller.transport.duration_ms", (time.time() - start_time) * 1000, {"provider": "YAHOO"})

        # 3. Invoke Payload Validator
        val_start = time.time()
        validation_result = self.validator.validate(transport_result)
        self.metrics.record_latency("poller.validator.duration_ms", (time.time() - val_start) * 1000, {"provider": "YAHOO"})

        if not validation_result.is_valid:
            self.logger.warning(f"Validation rejected [{ticker}]: {validation_result.reason}")
            self.document_store.quarantine_payload(
                source=f"YAHOO_{ticker}",
                payload=transport_result.payload,
                reason=validation_result.reason
            )
            self.metrics.increment_counter("poller.validation.rejected", tags={"reason": validation_result.reason})
            return

        # 4. Persist Immutable Payload (DocumentStore acts as Authoritative Factory)
        doc_start = time.time()
        try:
            artifact_ref: ArtifactReference = self.document_store.store_market_payload(
                provider="YAHOO",
                data_type="PRICE",
                ticker=ticker,
                payload=transport_result.payload
            )
        except Exception as e:
            self.dlq.route_to_dlq(envelope=None, exception=e, component="DocumentStore")
            return
            
        self.metrics.record_latency("poller.document_store.duration_ms", (time.time() - doc_start) * 1000, {})

        # 5. Append Observation Ledger
        ledger_start = time.time()
        self.observation_store.append_ledger_entry(artifact_ref, transport_result.diagnostics)
        self.metrics.record_latency("poller.observation_store.duration_ms", (time.time() - ledger_start) * 1000, {})

        # 6. Publish Raw Event via Reference (Claim Check)
        envelope = EventEnvelope(
            metadata=EventMetadata(
                topic=EventTopic.RAW_MARKET_INGESTED,
                schema_version="1.1",
                correlation_id=f"POLL-YAHOO-{int(start_time)}"
            ),
            payload={
                "ticker": ticker,
                "artifact_reference": artifact_ref,
                "validation_result": validation_result,
                "transport_diagnostics": transport_result.diagnostics
            }
        )
        self.event_bus.publish(EventTopic.RAW_MARKET_INGESTED, envelope)

        # 7. Final Operational Metrics
        total_duration = (time.time() - start_time) * 1000
        self.metrics.record_latency("poller.total_duration_ms", total_duration, {"provider": "YAHOO", "ticker": ticker})
        self.metrics.increment_counter("poller.success", tags={"provider": "YAHOO"})
