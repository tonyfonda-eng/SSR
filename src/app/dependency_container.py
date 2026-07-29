import os
import logging
from typing import Optional, Dict

from src.engine.event_bus import EventBus
from src.engine.legacy_bridge import LegacyEventBridge
from src.engine.transport import ResilientTransport
from src.engine.default_infrastructure import DefaultMetricsRecorder, DefaultDeadLetterQueue, DefaultConfigService
from src.engine.primitives import EventTopic

from src.app.monitoring.health import HealthService
from src.app.scheduling.scheduler import TaskScheduler
from src.app.ingestion.document_store import DocumentStore
from src.app.ingestion.sec_adapter import SECFilingAdapter

from src.operational.projection_store import ProjectionStore
from src.operational.worksheet_serializer import WorksheetSerializer
from src.operational.publisher import GoogleSheetsPublisher
from src.operational.projection_builder import ProjectionBuilder
from src.operational.publisher_task import GoogleSheetsPublisherTask

from src.operational.notifications.engine import NotificationRuleEngine
from src.operational.notifications.queue import NotificationQueueManager

from src.app.market.registry import MarketProviderRegistry
from src.app.market.repository import MarketRepository
from src.app.market.publisher import MarketMutationPublisher
from src.app.market.equality import PriceEqualityPolicy
from src.app.market.interfaces import ProviderBundle, ProviderDescriptor, MarketCapability

class DependencyContainer:
    def __init__(self):
        self.logger = logging.getLogger("SSR.Container")
        self.metrics: Optional[DefaultMetricsRecorder] = None
        self.dlq: Optional[DefaultDeadLetterQueue] = None
        self.config_service: Optional[DefaultConfigService] = None
        self.event_bus: Optional[LegacyEventBridge] = None
        self.market_registry: Optional[MarketProviderRegistry] = None
        self.market_repository: Optional[MarketRepository] = None
        self.mutation_publisher: Optional[MarketMutationPublisher] = None
        
        self.transport: Optional[ResilientTransport] = None
        self.document_store: Optional[DocumentStore] = None
        self.health_service: Optional[HealthService] = None
        self.task_scheduler: Optional[TaskScheduler] = None
        self.sec_adapter: Optional[SECFilingAdapter] = None
        self.projection_store: Optional[ProjectionStore] = None
        self.projection_builder: Optional[ProjectionBuilder] = None
        self.google_publisher: Optional[GoogleSheetsPublisher] = None
        self.publisher_task: Optional[GoogleSheetsPublisherTask] = None
        self.notification_queue: Optional[NotificationQueueManager] = None
        self.notification_engine: Optional[NotificationRuleEngine] = None

    def resolve_metrics(self) -> DefaultMetricsRecorder:
        if not self.metrics: self.metrics = DefaultMetricsRecorder()
        return self.metrics

    def resolve_dlq(self) -> DefaultDeadLetterQueue:
        if not self.dlq: self.dlq = DefaultDeadLetterQueue()
        return self.dlq

    def resolve_config_service(self) -> DefaultConfigService:
        if not self.config_service: self.config_service = DefaultConfigService()
        return self.config_service

    def resolve_event_bus(self) -> LegacyEventBridge:
        if not self.event_bus:
            pure_bus = EventBus(metrics=self.resolve_metrics(), dlq=self.resolve_dlq())
            self.event_bus = LegacyEventBridge(pure_bus=pure_bus, metrics=self.resolve_metrics())
        return self.event_bus

    def resolve_transport(self) -> ResilientTransport:
        if not self.transport: self.transport = ResilientTransport()
        return self.transport

    def resolve_document_store(self) -> DocumentStore:
        if not self.document_store: self.document_store = DocumentStore()
        return self.document_store

    def resolve_projection_store(self) -> ProjectionStore:
        if not self.projection_store: self.projection_store = ProjectionStore("ssr_projections.sqlite")
        return self.projection_store

    def resolve_health_service(self) -> HealthService:
        if not self.health_service: self.health_service = HealthService(self.resolve_projection_store())
        return self.health_service

    def resolve_task_scheduler(self) -> TaskScheduler:
        if not self.task_scheduler: self.task_scheduler = TaskScheduler()
        return self.task_scheduler

    def resolve_sec_adapter(self) -> SECFilingAdapter:
        if not self.sec_adapter: self.sec_adapter = SECFilingAdapter(self.resolve_event_bus())
        return self.sec_adapter

    def resolve_projection_builder(self) -> ProjectionBuilder:
        if not self.projection_builder:
            self.projection_builder = ProjectionBuilder(self.resolve_projection_store())
        return self.projection_builder

    def resolve_google_publisher(self, spreadsheet_id: str, credentials) -> GoogleSheetsPublisher:
        if not self.google_publisher:
            store = self.resolve_projection_store()
            serializer = WorksheetSerializer(projection_version="1.1.0")
            self.google_publisher = GoogleSheetsPublisher(spreadsheet_id, credentials, store, serializer)
        return self.google_publisher

    def resolve_publisher_task(self, spreadsheet_id: str) -> GoogleSheetsPublisherTask:
        if not self.publisher_task:
            pub = self.google_publisher or self.resolve_google_publisher(spreadsheet_id, None)
            self.publisher_task = GoogleSheetsPublisherTask(pub, self.resolve_health_service())
        return self.publisher_task

    def resolve_notification_queue(self, discord_webhook: Optional[str] = None, email_config: Optional[Dict] = None) -> NotificationQueueManager:
        if not self.notification_queue:
            self.notification_queue = NotificationQueueManager(discord_webhook, email_config)
        return self.notification_queue

    def resolve_notification_engine(self, discord_webhook: Optional[str] = None, email_config: Optional[Dict] = None) -> NotificationRuleEngine:
        if not self.notification_engine:
            queue = self.resolve_notification_queue(discord_webhook, email_config)
            self.notification_engine = NotificationRuleEngine(queue_manager=queue)
        return self.notification_engine

    def resolve_market_repository(self) -> MarketRepository:
        if not self.market_repository:
            self.market_repository = MarketRepository()
            self.market_repository.register_equality_policy("PRICE", PriceEqualityPolicy())
        return self.market_repository

    def resolve_mutation_publisher(self) -> MarketMutationPublisher:
        if not self.mutation_publisher:
            self.mutation_publisher = MarketMutationPublisher(
                repository=self.resolve_market_repository(),
                event_bus=self.resolve_event_bus()
            )
        return self.mutation_publisher

    def resolve_market_registry(self) -> MarketProviderRegistry:
        if not self.market_registry:
            bus = self.resolve_event_bus()
            self.market_registry = MarketProviderRegistry()
            
            publisher = self.resolve_mutation_publisher()
            bus.subscribe(EventTopic.OBS_MKT_SNAPSHOT, publisher.handle_observation)
            
            builder = self.resolve_projection_builder()
            if hasattr(builder, "handle_market_update"):
                bus.subscribe(EventTopic.OBJ_MKT_UPDATED, builder.handle_market_update)
            
        return self.market_registry

    def resolve_sec_poller(self):
        """Resolves the live engine scheduling task worker for SEC tracking."""
        from src.app.ingestion.sec_poller import SECPollerTask
        import inspect
        
        sig = inspect.signature(SECPollerTask.__init__)
        params = list(sig.parameters.keys())
        
        kwargs = {}
        if 'store' in params or 'document_store' in params:
            kwargs['store' if 'store' in params else 'document_store'] = self.resolve_document_store()
        if 'event_bus' in params:
            kwargs['event_bus'] = self.resolve_event_bus()
        if 'config' in params:
            kwargs['config'] = self.resolve_config_service()
        if 'metrics' in params:
            kwargs['metrics'] = self.resolve_metrics()
        if 'transport' in params or 'http_client' in params:
            kwargs['transport' if 'transport' in params else 'http_client'] = self.resolve_transport()
            
        # Fallback if positional matching is strictly needed
        if not kwargs:
            return SECPollerTask(self.resolve_document_store(), self.resolve_event_bus())
            
        return SECPollerTask(**kwargs)

    def resolve_newswire_monitor(self):
        """Resolves the dynamic spreadsheet-backed newswire monitoring task worker."""
        from src.app.ingestion.newswire_monitor import NewswireMonitorTask
        
        # Resolve spreadsheet capability automatically from current container definitions
        sheet_client = getattr(self, 'resolve_spreadsheet_client', lambda: getattr(self, 'spreadsheet_client', None))()
        
        return NewswireMonitorTask(
            config=self.resolve_config_service(),
            store=self.resolve_document_store(),
            event_bus=self.resolve_event_bus(),
            spreadsheet_client=sheet_client
        )
