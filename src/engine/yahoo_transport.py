import time
import logging
import requests
from typing import Dict, Any, Tuple
from src.engine.transport_policy import TransportPolicy, TransportResult

class YahooTransportPolicy(TransportPolicy):
    """
    Yahoo-specific transport boundary. Encapsulates crumb negotiation, session
    persistence, and CAPTCHA detection, exposing only neutral TransportResults.
    """
    
    def __init__(self):
        self.logger = logging.getLogger("SSR.YahooTransport")
        self._session = None
        self._crumb = None
        self._base_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }

    def prepare_session(self, session_context: Any = None) -> requests.Session:
        """Negotiates the Yahoo cookie and extracts the cryptographic crumb."""
        if self._session and self._crumb:
            return self._session

        self.logger.info("Negotiating Yahoo session cookie and crumb token...")
        self._session = requests.Session()
        self._session.headers.update(self._base_headers)
        
        try:
            # 1. Fetch tracking cookie (usually returns 404 but sets the cookie)
            self._session.get("https://fc.yahoo.com", timeout=5.0)
            
            # 2. Extract crumb
            response = self._session.get("https://query1.finance.yahoo.com/v1/test/getcrumb", timeout=5.0)
            if response.status_code == 200:
                self._crumb = response.text.strip()
                self.logger.debug(f"Successfully negotiated Yahoo crumb: {self._crumb[:3]}***")
            else:
                self.logger.warning(f"Crumb extraction failed with status: {response.status_code}")
                self._crumb = None
        except Exception as e:
            self.logger.error(f"Session negotiation network failure: {str(e)}")
            self._crumb = None
            
        return self._session

    def before_request(self, target: str, parameters: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Injects the crumb into the target URL if successfully negotiated."""
        if not self._session or not self._crumb:
            self.prepare_session()
            
        final_url = f"{target}&crumb={self._crumb}" if self._crumb and "?" in target else target
        return final_url, parameters

    def after_response(self, raw_response: requests.Response) -> TransportResult:
        """Translates the requests.Response into a framework-neutral TransportResult."""
        content_type = raw_response.headers.get("Content-Type", "").lower()
        success = raw_response.status_code == 200
        
        # Explicit CAPTCHA / Block Detection
        if "text/html" in content_type:
            text = raw_response.text.lower()
            if "captcha" in text or "cloudflare" in text:
                self.logger.error("CAPTCHA interception detected. IP reputation may be compromised.")
                success = False

        return TransportResult(
            success=success,
            payload=raw_response.text,
            metadata={"source": "YAHOO_V8", "content_type": content_type},
            diagnostics={
                "status_code": raw_response.status_code,
                "elapsed_ms": raw_response.elapsed.total_seconds() * 1000
            }
        )

    def recover(self, exception: Exception, attempt: int, config: Dict[str, Any]) -> bool:
        """Evaluates retry logic based on dynamically injected config thresholds."""
        max_retries = config.get("retries", 3)
        if attempt >= max_retries:
            return False
            
        # If rate limited (429) or forbidden (403 - bad crumb), force session rotation on next attempt
        if isinstance(exception, requests.exceptions.RequestException):
            response = getattr(exception, 'response', None)
            if response and response.status_code in (403, 429):
                self.logger.warning(f"Yahoo rejected request ({response.status_code}). Flushing session.")
                self._session = None
                self._crumb = None
                
        return True
