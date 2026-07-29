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
        "CALC.ANALYTICS.OPT.ASSIGNMENT_RISK",
        "CALC.PORT.POSITION_PNL"
    ]
    
    # 1. Initialize Notifier for severe PnL drawdowns
    notifier = NotificationRuleEngine()
    notifier.register_rule(AlertRule(
        rule_id="RULE.PORT.SEVERE_DRAWDOWN",
        target_object_id="OBJ.PORT.POSITION_PNL",
        field="result_value",
        operator="<",
        threshold=-500.00,  # Alert if the short call position bleeds more than $500
        destination="CONSOLE"
    ))
    
    ctx = orchestrator.bootstrap_context("EVT.2026.PORTFOLIO_TXNM", active_calcs)
    ctx.bus.subscribe(notifier.on_object_published)
    
    print("\n==================================================")
    print("[*] Hydrating Static Portfolio Record: Short Naked Call")
    
    # Sell to Open 10 TXNM Call Contracts at $2.00
    ctx.bus.publish("OBJ.PORT.POSITION_RECORD", {
        "ticker": "TXNM",
        "position_type": "short",
        "quantity": -10, 
        "average_entry_price": 2.00,
        "multiplier": 100.0
    })
    
    ctx.bus.publish("OBJ.OPT.OPTION_CONTRACT", {"option_type": "call", "strike": 45.0})
    
    print("\n[*] Simulating Market Tick: Underlying rallies, premium inflates")
    # A market tick arrives: The underlying jumped to $48, and the option premium spiked to $4.50
    ctx.bus.publish("OBJ.MKT.PRICE_SNAPSHOT", {"price": 48.00})
    ctx.bus.publish("OBJ.MKT.PREMIUM_SNAPSHOT", {"price": 4.50})
    
    # Extract the resulting Portfolio PnL to view the damage
    pnl_obj = ctx.calculation_results.get("OBJ.PORT.POSITION_PNL")
    if pnl_obj:
        print(f"\n[📊 LIVE PNL]: ${pnl_obj.result_value:,.2f}")
    
    print("==================================================")

if __name__ == "__main__":
    main()
