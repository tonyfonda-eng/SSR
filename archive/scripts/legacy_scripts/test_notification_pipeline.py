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
        "CALC.ANALYTICS.OPT.ASSIGNMENT_RISK"
    ]
    
    # 1. Initialize the Notification Matrix
    notifier = NotificationRuleEngine()
    
    # Rule A: Catch when option assignment risk spikes to a dangerous level
    notifier.register_rule(AlertRule(
        rule_id="RULE.OPT.ASSIGNMENT_THREAT",
        target_object_id="OBJ.ANALYTICS.OPT.ASSIGNMENT_PROBABILITY",
        field="result_value",
        operator=">",
        threshold=0.90,
        destination="CONSOLE"
    ))
    
    # 2. Bootstrap execution context
    ctx = orchestrator.bootstrap_context("EVT.2026.ALERT_TEST", active_calcs)
    
    # Link the notifier to the internal EventBus execution broadcast stream
    ctx.bus.subscribe(notifier.on_object_published)
    
    print("\n==================================================")
    print("[*] Scenario A: Safe Market Matrix (Time premium cushions options)")
    ctx.bus.publish("OBJ.OPT.OPTION_CONTRACT", {"option_type": "call", "strike": 40.0})
    ctx.bus.publish("OBJ.MKT.PRICE_SNAPSHOT", {"price": 42.00})
    ctx.bus.publish("OBJ.MKT.PREMIUM_SNAPSHOT", {"price": 3.50}) # Extrinsic = 1.50
    
    print("\n==================================================")
    print("[*] Scenario B: Aggressive ITM Cascade (Extrinsic value dry-up)")
    
    # Create a fresh context to clean historical execution memory blocks
    ctx_danger = orchestrator.bootstrap_context("EVT.2026.ALERT_DANGER", active_calcs)
    ctx_danger.bus.subscribe(notifier.on_object_published)
    
    ctx_danger.bus.publish("OBJ.OPT.OPTION_CONTRACT", {"option_type": "call", "strike": 40.0})
    ctx_danger.bus.publish("OBJ.MKT.PRICE_SNAPSHOT", {"price": 48.00})
    ctx_danger.bus.publish("OBJ.MKT.PREMIUM_SNAPSHOT", {"price": 8.05}) # Extrinsic = 0.05
    print("==================================================")

if __name__ == "__main__":
    main()
