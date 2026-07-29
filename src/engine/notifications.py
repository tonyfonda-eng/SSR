import json
from typing import Dict, Any, List, Callable

class AlertRule:
    def __init__(self, rule_id: str, target_object_id: str, field: str, operator: str, threshold: Any, destination: str):
        self.rule_id = rule_id
        self.target_object_id = target_object_id
        self.field = field
        self.operator = operator
        self.threshold = threshold
        self.destination = destination

    def evaluate(self, payload: Any) -> bool:
        # Extract the target value from either a raw dict or a Pydantic CalculationResult wrapper
        val = getattr(payload, self.field, None)
        if val is None and isinstance(payload, dict):
            val = payload.get(self.field)
            
        if val is None:
            return False

        if self.operator == ">": return val > self.threshold
        if self.operator == "<": return val < self.threshold
        if self.operator == "==": return val == self.threshold
        return False

class NotificationRuleEngine:
    """Subscribes directly to the EventBus to alert on threshold breaches."""
    def __init__(self):
        self.rules: List[AlertRule] = []
        self.dispatchers: Dict[str, Callable[[str], None]] = {
            "CONSOLE": lambda msg: print(f"\n[🔔 ALERT DISPATCHED TO CONSOLE] {msg}")
        }

    def register_rule(self, rule: AlertRule):
        self.rules.append(rule)

    def register_dispatcher(self, destination_name: str, callback: Callable[[str], None]):
        self.dispatchers[destination_name] = callback

    def on_object_published(self, object_id: str, payload: Any):
        for rule in self.rules:
            if rule.target_object_id == object_id:
                if rule.evaluate(payload):
                    # Unpack values for clean reporting metrics
                    inner_val = getattr(payload, 'result_value', payload)
                    msg = f"Rule {rule.rule_id} Breached: Matrix target {object_id}.{rule.field} reached {inner_val} (Threshold: {rule.operator} {rule.threshold})"
                    
                    dispatcher = self.dispatchers.get(rule.destination, self.dispatchers["CONSOLE"])
                    dispatcher(msg)
