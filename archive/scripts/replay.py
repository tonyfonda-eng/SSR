import sys
import os
import logging
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))
from src.app.dependency_container import DependencyContainer
from src.engine.primitives import EventTopic, EventEnvelope, EventMetadata, ArtifactReference
import hashlib

logging.basicConfig(level=logging.INFO, format='%(asctime)s - REPLAY - %(levelname)s - %(message)s')
logger = logging.getLogger("SSR.Replay")

def run_replay(file_path: str):
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        sys.exit(1)
        
    logger.info(f"Initiating forensic replay context execution for: {file_path}")
    
    container = DependencyContainer()
    event_bus = container.resolve_event_bus()
    
    # Trigger full market assembly root graph initialization
    market_registry = container.resolve_market_registry()
    market_repo = container.resolve_market_repository()
    
    sec_adapter = container.resolve_sec_adapter()
    builder = container.resolve_projection_builder()

    # Pull Alert Notification Configs
    discord_webhook = os.getenv("SSR_DISCORD_WEBHOOK")
    email_config = {
        "host": os.getenv("SSR_SMTP_HOST"),
        "port": os.getenv("SSR_SMTP_PORT", "587"),
        "user": os.getenv("SSR_SMTP_USER"),
        "password": os.getenv("SSR_SMTP_PASSWORD"),
        "sender": os.getenv("SSR_SMTP_SENDER"),
        "recipient": os.getenv("SSR_SMTP_RECIPIENT")
    }
    
    notification_engine = container.resolve_notification_engine(discord_webhook, email_config)
    queue_manager = container.resolve_notification_queue(discord_webhook, email_config)
    
    # Wire Core Target Bus Pipelines
    event_bus.subscribe("RAW.SEC.FILING_STORED", sec_adapter.handle_stored_filing)
    event_bus.subscribe("RAW.SEC.FILING_STORED", builder.handle_sec_filing)
    event_bus.subscribe("CALC.RISK.ASSIGNMENT", builder.handle_risk_calculation)
    event_bus.subscribe("CALC.RISK.ASSIGNMENT", notification_engine.evaluate)
    
    queue_manager.start_worker()

    # ==========================================
    # Scheduler Gateway Simulation Engine Check
    # ==========================================
    live_yahoo_connector = os.getenv("live_yahoo_connector", "false").lower() == "true"
    
    if live_yahoo_connector:
        logger.info("Bootstrap Trace: Scheduler attaching Yahoo poller task execution slot...")
        try:
            yahoo_poller = market_registry.get_poller("YAHOO")
            # Execute bounded poller check for a watch asset target (e.g., DSGR target)
            yahoo_poller.execute(ticker="DSGR", force=False)
        except Exception as ex:
            logger.error(f"Scheduled market data execution block trace fault: {str(ex)}")
    else:
        logger.info("Feature Flag [live_yahoo_connector] is disabled. Skipping market ingestion scheduler registration.")

    # Process SEC File Cache Target Artifact
    filename = os.path.basename(file_path)
    accession = filename.split('_')[0] if '_' in filename else "REPLAY_RUN"

    logger.info("Injecting forensic filing target artifact into system EventBus framework...")
    # Generate ArtifactReference Claim Check
    with open(file_path, "rb") as f:
        file_bytes = f.read()
    
    artifact = ArtifactReference(
        schema_version="1.0",
        provider="SEC",
        data_type="FILING",
        ticker="UNKNOWN",
        cache_path=file_path,
        sha256_hash=hashlib.sha256(file_bytes).hexdigest(),
        timestamp=time.time(),
        size_bytes=len(file_bytes)
    )

    envelope = EventEnvelope(
        metadata=EventMetadata(
            topic=EventTopic.RAW_SEC_FILING_STORED,
            schema_version="1.0",
            correlation_id=f"REPLAY-{accession}",
            is_replay=True
        ),
        payload={
            "artifact_reference": artifact,
            "accession_number": accession,
            "title": f"FORENSIC REPLAY RUN: {filename}",
            "source": "REPLAY_CLI"
        }
    )
    
    event_bus.publish(EventTopic.RAW_SEC_FILING_STORED, envelope)
    
    logger.info("DAG execution complete. Local projection states stabilized inside SQLite.")
    
    try:
        sheet_id = os.getenv("SSR_SPREADSHEET_ID")
        if not sheet_id:
            logger.error("No SSR_SPREADSHEET_ID found inside terminal execution window environments.")
        else:
            pub_task = container.resolve_publisher_task(sheet_id)
            print("\n--- Sweeping Cockpit Model Projections ---")
            pub_task.execute()
    except Exception as e:
        logger.error(f"Google Sheets transmission failed to commit: {str(e)}")

    time.sleep(1.0)
    queue_manager.stop_worker()
    logger.info("Forensic operational runtime execution closed cleanly.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 replay.py <path_to_cached_html_file>")
        sys.exit(1)
    run_replay(sys.argv[1])
