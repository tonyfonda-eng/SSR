from src.engine.event_bus import EventBus
from src.engine.primitives import EventTopic, EventEnvelope, EventMetadata, MutationStatus
from src.app.market.interfaces import MarketStateWriter

class MarketMutationPublisher:
    """Translates passive Repository mutations into active EventBus broadcasts."""
    
    def __init__(self, repository: MarketStateWriter, event_bus: EventBus):
        self.repository = repository
        self.event_bus = event_bus

    def handle_observation(self, envelope: EventEnvelope) -> None:
        mutation_result = self.repository.apply_observation(envelope.payload)
        
        if mutation_result.status == MutationStatus.REJECTED:
            return

        topic = EventTopic.OBJ_MKT_UPDATED if mutation_result.status == MutationStatus.UPDATED else EventTopic.OBJ_MKT_UNCHANGED
        
        outbound_env = EventEnvelope(
            metadata=EventMetadata(
                topic=topic,
                schema_version="1.0",
                correlation_id=envelope.metadata.correlation_id,
                causation_id=envelope.metadata.event_id,
                is_replay=envelope.metadata.is_replay
            ),
            payload=mutation_result
        )
        
        self.event_bus.publish(topic, outbound_env)
