import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.engine.orchestrator import ExecutionOrchestrator
from src.engine.ingestion import MarketIngestionService
from src.engine.transport import HardenedHTTPTransport
from src.engine.adapters.sec import SECEDGARConnector, SECEDGARAdapter
from src.engine.notifications import NotificationRuleEngine, AlertRule

def main():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    orchestrator = ExecutionOrchestrator(root)
    transport = HardenedHTTPTransport()
    
    # Init SEC Pipeline
    sec_conn = SECEDGARConnector(transport)
    sec_adapt = SECEDGARAdapter()
    
    # We pass None for standard adapters here since we are only testing the SEC endpoint
    ingestion = MarketIngestionService(None, None, orchestrator.validator)
    
    # 1. Setup Notification Engine to alert on new filings
    notifier = NotificationRuleEngine()
    
    # Custom dispatcher to print the exact SEC URL
    def print_filing_alert(msg):
        print(f"\n[🚨 SEC EVENT DETECTED] {msg}")

    notifier.register_dispatcher("SEC_ALERT", print_filing_alert)
    
    # A rule that checks if a filing form_type equals 8-K
    notifier.register_rule(AlertRule(
        rule_id="RULE.CORP.NEW_8K_FILED",
        target_object_id="ANY", # We will manually handle this via the bus
        field="form_type",
        operator="==",
        threshold="8-K",
        destination="SEC_ALERT"
    ))
    
    # We must patch the Notification Engine slightly for this script to allow prefix matching on object_ids
    # so we can catch dynamically generated OBJ.DOC.FILING.* keys.
    def custom_on_publish(object_id, payload):
        if object_id.startswith("OBJ.DOC.FILING"):
            for rule in notifier.rules:
                if rule.evaluate(payload):
                    msg = f"New {payload['form_type']} filed for {payload['ticker']}! Link: {payload['document_url']}"
                    notifier.dispatchers[rule.destination](msg)
                    
    ctx = orchestrator.bootstrap_context("EVT.2026.SEC_MONITOR", [])
    ctx.bus.subscribe(custom_on_publish)
    
    print("\n==================================================")
    print("[*] Initiating SEC EDGAR RSS Poll for Corporate Actions...")
    
    # Execute Live Pull for CZR (Caesars Entertainment)
    ingestion.ingest_sec_filings(ctx, sec_conn, sec_adapt, "CZR", form_type="8-K")
    
    print("==================================================")

if __name__ == "__main__":
    main()
