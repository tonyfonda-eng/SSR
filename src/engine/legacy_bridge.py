import time
import uuid
import logging
import inspect
from typing import Any, Callable
from src.engine.event_bus import EventBus
from src.engine.primitives import EventTopic, EventEnvelope, EventMetadata
from src.engine.infrastructure import MetricsRecorder

class LegacyEventBridge:
    """
    Anti-Corruption Layer buffering legacy structures from the strict baseline.
    Destined for deletion once legacy_bridge.publish metrics reach zero.
    """
    
    _ALIAS_MAP = {
        "RAW.SEC.FILING_STORED": EventTopic.RAW_SEC_FILING_STORED,
        "CALC.RISK.ASSIGNMENT": EventTopic.CALC_RISK_ASSIGNMENT,
        "RAW.MARKET.YAHOO": EventTopic.RAW_MARKET_INGESTED,
        "OBS.MKT.SNAPSHOT": EventTopic.OBS_MKT_SNAPSHOT,
        "OBJ.MKT.UPDATED": EventTopic.OBJ_MKT_UPDATED,
        "OBJ.MKT.UNCHANGED": EventTopic.OBJ_MKT_UNCHANGED
    }

    def __init__(self, pure_bus: EventBus, metrics: MetricsRecorder):
        self.pure_bus = pure_bus
        self.metrics = metrics
        self.logger = logging.getLogger("SSR.LegacyBridge")

    def _resolve_topic(self, topic_str: str) -> EventTopic:
        if topic_str in self._ALIAS_MAP:
            return self._ALIAS_MAP[topic_str]
        
        try:
            return EventTopic(topic_str)
        except ValueError:
            self.logger.critical(f"Legacy bridge rejected unknown topic alias: {topic_str}")
            raise ValueError(f"Unmapped legacy topic string: {topic_str}")

    def publish(self, topic: Any, payload: Any) -> None:
        self.metrics.increment_counter("legacy_bridge.publish")
        
        if isinstance(topic, EventTopic) and isinstance(payload, EventEnvelope):
            self.pure_bus.publish(topic, payload)
            return

        topic_str = topic.value if isinstance(topic, EventTopic) else str(topic)
        enum_topic = self._resolve_topic(topic_str)

        correlation_id = None
        is_replay = False
        if isinstance(payload, dict):
            correlation_id = payload.get("correlation_id")
            is_replay = payload.get("is_replay", False)
            
        if not correlation_id:
            correlation_id = f"LEGACY-TR-{uuid.uuid4().hex[:8]}"

        meta = EventMetadata(
            topic=enum_topic,
            schema_version="1.0-legacy-bridge",
            correlation_id=correlation_id,
            is_replay=is_replay
        )
        envelope = EventEnvelope(metadata=meta, payload=payload)
        
        self.logger.debug(f"Bridging legacy publish: [{topic_str}] -> {enum_topic.name}")
        self.pure_bus.publish(enum_topic, envelope)

    def subscribe(self, topic: Any, callback: Callable) -> None:
        self.metrics.increment_counter("legacy_bridge.subscribe")
        topic_str = topic.value if isinstance(topic, EventTopic) else str(topic)
        enum_topic = self._resolve_topic(topic_str)
        
        sig = inspect.signature(callback)
        parameters = list(sig.parameters.values())
        non_self_params = [p for p in parameters if p.name != 'self']
        
        # Check if callback is a native EventEnvelope handler
        is_native_envelope = False
        if len(non_self_params) == 1:
            param = non_self_params[0]
            if param.name in ('envelope', 'env') or 'EventEnvelope' in str(param.annotation):
                is_native_envelope = True

        if is_native_envelope:
            # Pass the full EventEnvelope directly without unpacking
            self.pure_bus.subscribe(enum_topic, callback)
            self.logger.debug(f"Bridged native subscription: {enum_topic.name} -> {callback.__name__}")
        else:
            # Legacy translation adapter for (topic, payload) or (payload)
            expects_two_args = len(non_self_params) >= 2
            def legacy_adapter(envelope: EventEnvelope) -> None:
                if expects_two_args:
                    callback(topic_str, envelope.payload)
                else:
                    callback(envelope.payload)

            self.pure_bus.subscribe(enum_topic, legacy_adapter)
            self.logger.debug(f"Bridged legacy subscription wrapper: {enum_topic.name} -> {callback.__name__}")
