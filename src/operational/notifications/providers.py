import logging
import smtplib
from email.message import EmailMessage
from abc import ABC, abstractmethod
from typing import Optional
from src.engine.transport import ResilientTransport, TransportPolicy, ExpectedMediaType
from src.operational.notifications.models import Alert

class DeliveryProvider(ABC):
    """Abstract interface for all notification delivery channels."""
    @abstractmethod
    def send(self, alert: Alert) -> bool:
        pass

class DiscordProvider(DeliveryProvider):
    """Dispatches alerts to a Discord channel via Webhook."""
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
        self.transport = ResilientTransport()
        self.policy = TransportPolicy(
            name="DISCORD_WEBHOOK",
            max_retries=2,
            base_backoff=1.0,
            expected_media=ExpectedMediaType.ANY
        )
        self.logger = logging.getLogger("SSR.DiscordProvider")

    def send(self, alert: Alert) -> bool:
        if not self.webhook_url:
            return False
            
        color_map = {"INFO": 3447003, "WARNING": 16776960, "CRITICAL": 15158332}

        payload = {
            "embeds": [{
                "title": f"🚨 SSR Alert: {alert.ticker}",
                "color": color_map.get(alert.severity.name, 3447003),
                "fields": [
                    {"name": "Rule Fired", "value": alert.rule_fired, "inline": True},
                    {"name": "Value Triggered", "value": str(alert.value), "inline": True},
                    {"name": "State", "value": alert.lifecycle_state.name, "inline": True},
                    {"name": "Correlation ID", "value": f"`{alert.correlation_id}`", "inline": False}
                ],
                "footer": {"text": f"Dependency Hash: {alert.dependency_hash[:8]}"},
                "timestamp": alert.timestamp
            }]
        }

        try:
            response = self.transport.session.post(
                self.webhook_url, json=payload, timeout=self.policy.timeout
            )
            response.raise_for_status()
            return True
        except Exception as e:
            self.logger.error(f"Discord delivery failed for {alert.alert_id}: {str(e)}")
            alert.last_error = str(e)
            return False

class EmailProvider(DeliveryProvider):
    """Dispatches alerts via SMTP Email."""
    def __init__(self, host: str, port: int, user: Optional[str], password: Optional[str], sender: str, recipient: str):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.sender = sender
        self.recipient = recipient
        self.logger = logging.getLogger("SSR.EmailProvider")

    def send(self, alert: Alert) -> bool:
        if not all([self.host, self.sender, self.recipient]):
            return False

        msg = EmailMessage()
        msg['Subject'] = f"🚨 SSR Alert: {alert.ticker} [{alert.severity.name}]"
        msg['From'] = self.sender
        msg['To'] = self.recipient
        
        body = f"""SSR Automated Alert
        
Ticker: {alert.ticker}
Rule Fired: {alert.rule_fired}
Value Triggered: {alert.value}
Lifecycle State: {alert.lifecycle_state.name}

Correlation ID: {alert.correlation_id}
Dependency Hash: {alert.dependency_hash}
Timestamp: {alert.timestamp}
"""
        msg.set_content(body)

        try:
            with smtplib.SMTP(self.host, self.port) as server:
                server.starttls()
                if self.user and self.password:
                    server.login(self.user, self.password)
                server.send_message(msg)
            return True
        except Exception as e:
            self.logger.error(f"Email delivery failed for {alert.alert_id}: {str(e)}")
            alert.last_error = str(e)
            return False
