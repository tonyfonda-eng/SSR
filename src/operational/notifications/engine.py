import logging

class NotificationRuleEngine:
    """Evaluates real-time risk scores against watched threshold boundaries."""
    
    def __init__(self, queue_manager):
        self.queue = queue_manager
        self.logger = logging.getLogger("SSR.NotificationEngine")
        self.risk_threshold = 0.90 # Safe default threshold anchor

    def evaluate(self, event_type: str, payload: any):
        """Interprets incoming calculation frames."""
        ticker = getattr(payload, "ticker", "UNKNOWN")
        result_value = getattr(payload, "result_value", 0.0)
        
        if result_value >= self.risk_threshold:
            self.logger.warning(f"Risk event breach detected for {ticker}: {result_value} >= {self.risk_threshold}")
            self.queue.enqueue_alert(
                ticker=ticker,
                title=f"Assignment Risk Threshold Breached for {ticker}",
                description=f"Calculated Assignment Risk factor is currently sitting at {round(result_value, 4)}. Immediate review required.",
                critical=True
            )

    def handle_config_update(self, event_type: str, new_config: dict):
        """Listens for configuration updates to update thresholds dynamically."""
        if "assignment_threshold" in new_config:
            self.risk_threshold = float(new_config["assignment_threshold"])
            self.logger.info(f"Notification engine rule state hot-reloaded. Threshold: {self.risk_threshold}")
