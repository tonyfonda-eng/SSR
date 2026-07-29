import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.engine.orchestrator import ExecutionOrchestrator
from src.engine.ingestion import MarketIngestionService
from src.engine.transport import HardenedHTTPTransport
from src.engine.adapters.yahoo import YahooFinanceConnector, YahooFinanceAdapter
from src.engine.runtime import ExecutionContext

def main():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    orchestrator = ExecutionOrchestrator(root)
    
    # Init HTTP client layers completely unified
    transport = HardenedHTTPTransport()
    connector = YahooFinanceConnector(transport)
    adapter = YahooFinanceAdapter()
    
    ingestion_service = MarketIngestionService(connector, adapter, orchestrator.validator)
    
    print("\n==================================================")
    ctx = ExecutionContext("EVT.2026.LIVE_CHAIN_RUN")
    
    print("[*] Pulling live underlying asset pricing...")
    ingestion_service.ingest_price(ctx, "CZR")
    
    print("[*] Dispatching request for live options chain matrix...")
    ingestion_service.ingest_option_chain(ctx, "CZR")
    
    print(f"\n[✓] Context Successfully Hydrated.")
    print(f"Total Live Market State Objects Monitored: {len(ctx.market_snapshots)}")
    print("==================================================")

if __name__ == "__main__":
    main()
