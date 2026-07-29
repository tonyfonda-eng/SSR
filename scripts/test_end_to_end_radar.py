import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.engine.orchestrator import ExecutionOrchestrator
from src.engine.extraction import RegulatoryExtractionEngine
from src.engine.notifications import NotificationRuleEngine, AlertRule

def main():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    orchestrator = ExecutionOrchestrator(root)
    
    # 1. Map out our complete tracking matrix
    active_calcs = [
        "CALC.OBJ.OPT.INTRINSIC_VALUE",
        "CALC.OBJ.OPT.EXTRINSIC_VALUE",
        "CALC.MNA.OPT.MERGER_PAYOFF"
    ]
    
    # 2. Boot Notification Rules
    notifier = NotificationRuleEngine()
    notifier.register_rule(AlertRule(
        rule_id="RULE.RADAR.TERMINAL_ALERT",
        target_object_id="OBJ.MNA.OPT.TERMINAL_PAYOFF",
        field="result_value",
        operator="<",
        threshold=0.00, # Alert immediately if the terminal deal math turns negative
        destination="CONSOLE"
    ))
    
    # 3. Initialize Core Extraction Service
    extractor_service = RegulatoryExtractionEngine(orchestrator.validator)
    
    # 4. Bootstrap clean context
    ctx = orchestrator.bootstrap_context("EVT.2026.RADAR_E2E_RUN", active_calcs)
    ctx.bus.subscribe(notifier.on_object_published)
    
    print("\n==================================================================")
    print("[*] PHASE 1: Initializing Live Trading Book Inventory")
    # Inventory: You sold 10 CZR calls at the $40.00 Strike for an initial premium of $1.50
    ctx.bus.publish("OBJ.PORT.POSITION_RECORD", {
        "ticker": "CZR",
        "position_type": "short",
        "quantity": -10,
        "average_entry_price": 1.50,
        "multiplier": 100.0
    })
    ctx.bus.publish("OBJ.OPT.OPTION_CONTRACT", {"option_type": "call", "strike": 40.00})
    
    # Current market conditions: Stock trading at $38.00 (Out-of-the-money, safe position)
    ctx.bus.publish("OBJ.MKT.PRICE_SNAPSHOT", {"price": 38.00})
    
    print("\n==================================================================")
    print("[*] PHASE 2: Live Document Ingestion Event Captured")
    # Simulate the structural filing object passing across the wire from our SEC feed
    simulated_filing = {
        "ticker": "CZR",
        "form_type": "8-K",
        "accession_number": "0001193125-26-000042",
        "document_url": "https://www.sec.gov/Archives/edgar/data/czr/8k.txt"
    }
    ctx.bus.publish("OBJ.DOC.SEC_FILING_ARRIVED", simulated_filing)
    
    print("\n==================================================================")
    print("[*] PHASE 3: Triggering Playbook Parsing Rule Matrix")
    # Execute the text parser extraction pipeline against the filing target
    extractor_service.run_uni_consideration_playbook(ctx, simulated_filing)
    
    print("\n==================================================================")
    print("[*] PHASE 4: Extracting Active Context Calculation Metrics")
    terminal_pnl = ctx.calculation_results.get("OBJ.MNA.OPT.TERMINAL_PAYOFF")
    if terminal_pnl:
        print(f"  - Calculated Terminal PnL Variance: ${terminal_pnl.result_value:,.2f}")
    print("==================================================================\n")

if __name__ == "__main__":
    main()
