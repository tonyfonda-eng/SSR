import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.engine.orchestrator import ExecutionOrchestrator
from src.engine.notifications import NotificationRuleEngine, AlertRule

def main():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    orchestrator = ExecutionOrchestrator(root)
    
    active_calcs = [
        "CALC.OBJ.OPT.INTRINSIC_VALUE",
        "CALC.OBJ.OPT.EXTRINSIC_VALUE",
        "CALC.PORT.POSITION_PNL",
        "CALC.MNA.OPT.MERGER_PAYOFF"
    ]
    
    # 1. Initialize Notifier for fatal M&A settlement blowouts
    notifier = NotificationRuleEngine()
    notifier.register_rule(AlertRule(
        rule_id="RULE.MNA.TERMINAL_LOSS",
        target_object_id="OBJ.MNA.OPT.TERMINAL_PAYOFF",
        field="result_value",
        operator="<",
        threshold=-1000.00,  # Alert if terminal buyout settlement loses more than $1,000
        destination="CONSOLE"
    ))
    
    ctx = orchestrator.bootstrap_context("EVT.2026.LXP_BUYOUT", active_calcs)
    ctx.bus.subscribe(notifier.on_object_published)
    
    print("\n==================================================")
    print("[*] STEP 1: Establishing Pre-Deal Portfolio State")
    
    # You sell 20 naked calls on LXP at the $12.50 strike for $0.40 premium
    ctx.bus.publish("OBJ.PORT.POSITION_RECORD", {
        "ticker": "LXP",
        "position_type": "short",
        "quantity": -20, 
        "average_entry_price": 0.40,
        "multiplier": 100.0
    })
    ctx.bus.publish("OBJ.OPT.OPTION_CONTRACT", {"option_type": "call", "strike": 12.50})
    ctx.bus.publish("OBJ.MKT.PRICE_SNAPSHOT", {"price": 11.20})
    
    print("\n[*] STEP 2: SEC EDGAR 8-K Hits the Wire")
    print("    -> NLP Pipeline extracts definitive all-cash buyout terms.")
    
    # The Ingestion service verifies the CandidateAssertion and publishes the extracted cash fact:
    buyout_price = 15.00
    print(f"    -> [FACT PUBLISHED] OBJ.FIN.CASH_CONSIDERATION = ${buyout_price:.2f}")
    
    # This single fact publication will trigger the reactive EventBus to evaluate terminal payoff
    ctx.bus.publish("OBJ.FIN.CASH_CONSIDERATION", buyout_price)
    
    # Output the final calculation
    payoff_obj = ctx.calculation_results.get("OBJ.MNA.OPT.TERMINAL_PAYOFF")
    if payoff_obj:
        print(f"\n[🏛️ TERMINAL SETTLEMENT PNL]: ${payoff_obj.result_value:,.2f}")
    
    print("==================================================")

if __name__ == "__main__":
    main()
