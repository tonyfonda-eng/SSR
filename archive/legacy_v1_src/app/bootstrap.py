import os
import sys
import time
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from src.app.dependency_container import DependencyContainer

def setup_structured_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    return logging.getLogger("SSR.Bootstrap")

def bootstrap_application() -> DependencyContainer:
    logger = setup_structured_logging()
    logger.info("Initiating SSR Application Bootstrap Sequence...")

    spreadsheet_id = os.getenv("SSR_SPREADSHEET_ID")
    discord_webhook = os.getenv("SSR_DISCORD_WEBHOOK")
    mock_credentials = None 
    
    email_config = {
        "host": os.getenv("SSR_SMTP_HOST"),
        "port": os.getenv("SSR_SMTP_PORT", "587"),
        "user": os.getenv("SSR_SMTP_USER"),
        "password": os.getenv("SSR_SMTP_PASSWORD"),
        "sender": os.getenv("SSR_SMTP_SENDER"),
        "recipient": os.getenv("SSR_SMTP_RECIPIENT")
    }

    container = DependencyContainer()

    # Core Infrastructure
    event_bus = container.resolve_event_bus()
    transport = container.resolve_transport()
    config_service = container.resolve_config_service()
    health_service = container.resolve_health_service()
    
    # Ingestion Core components
    document_store = container.resolve_document_store()
    sec_poller = container.resolve_sec_poller()
    sec_adapter = container.resolve_sec_adapter()
    newswire_monitor = container.resolve_newswire_monitor()
    rule_engine = getattr(container, 'resolve_rule_engine', lambda: getattr(container, 'rule_engine', None))()

    # Bind Ingestion Routing: Storage events fire the Extraction Adapter
    event_bus.subscribe("RAW.SEC.FILING_STORED", sec_adapter.handle_stored_filing)
    
    # Bind Ingestion Routing: Newswire events trigger adaptation/notifications matrix
    if hasattr(container, 'resolve_newswire_adapter'):
        newswire_adapter = container.resolve_newswire_adapter()
        event_bus.subscribe("RAW.NEWSWIRE.INGESTED", newswire_adapter.handle_stored_article)

    # Notifications pipeline cross-wiring
    queue_manager = None
    if discord_webhook or email_config["host"]:
        queue_manager = container.resolve_notification_queue(discord_webhook, email_config)
        notification_engine = container.resolve_notification_engine(discord_webhook, email_config)
        
        # Core calculation outcomes trigger rule updates
        def _unwrap_and_evaluate(*args, **kwargs):
            # Flexible signature to bypass strict EventBus positional requirements
            envelope = args[-1] if args else kwargs.get('payload', kwargs.get('envelope'))
            actual_payload = getattr(envelope, "payload", envelope)
            notification_engine.evaluate("CALC_RISK_ASSIGNMENT", actual_payload)

        event_bus.subscribe(EventTopic.CALC_RISK_ASSIGNMENT, _unwrap_and_evaluate)
        event_bus.subscribe("EVT.CONFIG.UPDATED", notification_engine.handle_config_update)
        logger.info("Notification engine linked to calculation and configuration event tracks.")

    # Initialize Baseline configuration state
    config_service.load_defaults()
    
    # Scheduling matrix configuration
    scheduler = container.resolve_task_scheduler()
    
    # Live task hooks injection
    scheduler.schedule_task("SEC_Poller", interval_seconds=60, target_callable=sec_poller.execute)
    
    # Schedule the spreadsheet-backed multi-source newswire loop
    if newswire_monitor:
        scheduler.schedule_task(
            "Newswire_Sources_Poller", 
            interval_seconds=60, 
            target_callable=lambda: newswire_monitor.execute(spreadsheet_id)
        )
    
    def telemetry_heartbeat():
        health_service.report_success("HealthWorker", latency_ms=0.8)
        
    scheduler.schedule_task("HealthWorker", interval_seconds=5, target_callable=telemetry_heartbeat)

    logger.info("SSR Application Bootstrap Complete.")
    return container

def run_daemon():
    container = bootstrap_application()
    logger = logging.getLogger("SSR.Runtime")
    
    scheduler = container.resolve_task_scheduler()
    queue_manager = container.notification_queue
    
    if queue_manager:
        queue_manager.start_worker()
    scheduler.start()
    
    logger.info("SSR Continuous Runtime Online. Ingestion active. Press Ctrl+C to terminate.")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.warning("\nSIGINT caught. Cleaning pipeline states...")
    finally:
        scheduler.stop()
        if queue_manager:
            queue_manager.stop_worker()
        logger.info("System gracefully unmounted.")
        sys.exit(0)

if __name__ == "__main__":
    run_daemon()
