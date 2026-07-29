import time
import logging
from typing import Dict, List, Callable
from src.engine.primitives import EventTopic, EventEnvelope
from src.engine.infrastructure import MetricsRecorder, DeadLetterQueue

class EventBus:
    """
    Strict, envelope-only event distribution matrix.
    Enforces topic matching, schema validation, and subscriber isolation.
    """
    
    def __init__(self, metrics: MetricsRecorder, dlq: DeadLetterQueue):
        self.logger = logging.getLogger("SSR.EventBus")
        self.metrics = metrics
        self.dlq = dlq
        self._subscribers: Dict[EventTopic, List[Callable[[EventEnvelope], None]]] = {}

    def subscribe(self, topic: EventTopic, callback: Callable[[EventEnvelope], None]) -> None:
        if not isinstance(topic, EventTopic):
            raise TypeError(f"Subscription failed: topic must be an EventTopic enum, got {type(topic)}")
            
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        self._subscribers[topic].append(callback)
        self.logger.debug(f"Subscription locked: {topic.name} tied to {callback.__name__}")

    def publish(self, topic: EventTopic, envelope: EventEnvelope) -> None:
        # ==========================================
        # Precondition Validations
        # ==========================================
        if not isinstance(envelope, EventEnvelope):
            raise TypeError("EventBus strictly requires EventEnvelope instances.")
        if not isinstance(topic, EventTopic):
            raise TypeError("EventBus routing requires an explicit EventTopic enum.")
        if envelope.metadata.topic != topic:
            raise ValueError(f"Topic mismatch: Route {topic.name} != Envelope {envelope.metadata.topic.name}")
        if not envelope.metadata.schema_version:
            raise ValueError("Envelope rejected: Missing mandatory schema_version.")
        if not envelope.metadata.correlation_id:
            raise ValueError("Envelope rejected: Missing mandatory correlation_id.")
        if envelope.payload is None:
            raise ValueError("Envelope rejected: Payload cannot be None.")

        # ==========================================
        # Delivery & Subscriber Isolation
        # ==========================================
        start_time = time.time()
        subscribers = self._subscribers.get(topic, [])
        self.metrics.increment_counter("eventbus.publish.attempt", tags={"topic": topic.name})
        
        if not subscribers:
            self.logger.debug(f"Event published to empty room: {topic.name}")
            return

        failures = 0
        for callback in subscribers:
            try:
                callback(envelope)
            except Exception as e:
                failures += 1
                self.logger.error(f"Subscriber exception on [{topic.name}] in {callback.__name__}: {str(e)}")
                self.dlq.route_to_dlq(envelope=envelope, exception=e, component=f"EventBusSubscriber:{callback.__name__}")

        # ==========================================
        # Operational Telemetry
        # ==========================================
        duration_ms = (time.time() - start_time) * 1000
        self.metrics.record_latency("eventbus.publish.duration_ms", duration_ms, {"topic": topic.name})
        self.metrics.increment_counter("eventbus.publish.delivered", len(subscribers) - failures, {"topic": topic.name})
        if failures > 0:
            self.metrics.increment_counter("eventbus.publish.failures", failures, {"topic": topic.name})
