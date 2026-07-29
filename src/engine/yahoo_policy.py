import time
import random
import logging
import requests
from typing import Dict, Any, Optional

class YahooTransportPolicy:
    """
    Provider-specific transport boundary for Yahoo Finance.
    Handles session rotation, crumb negotiation, CAPTCHA detection, and jittered backoff.
    """
    
    def __init__(self):
        self.logger = logging.getLogger("SSR.YahooTransport")
        self._session: Optional[requests.Session] = None
        self._crumb: Optional[str] = None
        self._max_retries = 3
        self._base_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }

    def _rotate_session(self) -> None:
        """Flushes the active TCP pool and renegotiates the Yahoo cookie/crumb handshake."""
        self.logger.info("Negotiating new Yahoo session cookie and crumb...")
        if self._session:
            self._session.close()
            
        self._session = requests.Session()
        self._session.headers.update(self._base_headers)
        
        try:
            # 1. Fetch the tracking cookie (Usually returns 404, but sets the cookie)
            self._session.get("https://fc.yahoo.com", timeout=5.0)
            
            # 2. Extract the cryptographic crumb
            crumb_response = self._session.get("https://query1.finance.yahoo.com/v1/test/getcrumb", timeout=5.0)
            if crumb_response.status_code == 200:
                self._crumb = crumb_response.text.strip()
                self.logger.info(f"Successfully negotiated Yahoo crumb: {self._crumb[:3]}***")
            else:
                self.logger.warning(f"Failed to extract crumb, status code: {crumb_response.status_code}")
                self._crumb = None
        except Exception as e:
            self.logger.error(f"Session rotation network failure: {str(e)}")
            self._crumb = None

    def _detect_captcha(self, response: requests.Response) -> bool:
        """Scans response payload for explicit scraper firewalls."""
        content_type = response.headers.get("Content-Type", "")
        if "text/html" in content_type:
            text = response.text.lower()
            if "captcha" in text or "cloudflare" in text or "recaptcha" in text:
                return True
        return False

    def execute_get(self, url: str, timeout: float = 5.0) -> requests.Response:
        """Executes a GET request using aggressive backoff, jitter, and automated session recovery."""
        if not self._session or not self._crumb:
            self._rotate_session()

        # Inject crumb into URL if successfully negotiated
        target_url = f"{url}&crumb={self._crumb}" if self._crumb and "?" in url else url

        for attempt in range(1, self._max_retries + 1):
            try:
                response = self._session.get(target_url, timeout=timeout)
                
                # Check for rate limiting (429) or Forbidden (403 usually means bad crumb)
                if response.status_code in (403, 429):
                    self.logger.warning(f"Yahoo rejected request ({response.status_code}). Session may be burned.")
                    self._rotate_session()
                    raise requests.exceptions.RequestException(f"HTTP {response.status_code}")
                
                # Check for CAPTCHA interception
                if self._detect_captcha(response):
                    self.logger.error("CAPTCHA interception detected. IP reputation may be compromised.")
                    self._rotate_session()
                    raise requests.exceptions.RequestException("CAPTCHA Blocked")

                return response

            except requests.exceptions.RequestException as e:
                if attempt == self._max_retries:
                    self.logger.error(f"Yahoo transport policy exhausted all retries for {target_url}")
                    raise e
                
                # Exponential backoff with cryptographic uniform jitter
                sleep_time = (2 ** attempt) + random.uniform(0, 1)
                self.logger.warning(f"Yahoo transport failure: {str(e)}. Retrying in {sleep_time:.2f}s (Attempt {attempt}/{self._max_retries})")
                time.sleep(sleep_time)
                
        raise Exception("YahooTransportPolicy failed unexpectedly.")
