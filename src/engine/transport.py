import time
import random
import uuid
import json
import os
from datetime import datetime
from urllib.parse import urlparse
import requests
from requests.exceptions import RequestException, Timeout
from dataclasses import dataclass, field
from typing import Set
from enum import Enum

# --- EXCEPTION TAXONOMY ---
class RadarError(Exception): pass
class TransportError(RadarError): pass
class CircuitOpenError(TransportError): pass
class PayloadError(RadarError): pass

class ExpectedMediaType(Enum):
    JSON = "json"
    XML = "xml"
    PDF = "pdf"
    HTML = "html"
    ANY = "any"

@dataclass
class TransportPolicy:
    name: str
    max_retries: int = 3
    base_backoff: float = 1.0
    timeout: float = 10.0
    retryable_codes: Set[int] = field(default_factory=lambda: {429, 500, 502, 503, 504})
    expected_media: ExpectedMediaType = ExpectedMediaType.ANY

class ResilientTransport:
    def __init__(self, quarantine_dir: str = "quarantine"):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "SpecialSituationsRadar_v1.0 (Research)"})
        self.circuit_breakers = {} 
        self.quarantine_dir = quarantine_dir
        if not os.path.exists(quarantine_dir):
            os.makedirs(quarantine_dir)

    def get(self, url: str, policy: TransportPolicy) -> requests.Response:
        req_id = str(uuid.uuid4())[:8]
        hostname = urlparse(url).netloc
        
        if time.time() < self.circuit_breakers.get(hostname, 0):
            self._log("transport_circuit_open", req_id, hostname, policy.name, error="Fast failing")
            raise CircuitOpenError(f"Circuit open for {hostname}")

        retries = 0
        while retries <= policy.max_retries:
            start_time = time.time()
            try:
                response = self.session.get(url, timeout=policy.timeout)
                duration = round(time.time() - start_time, 3)
                
                if response.status_code in policy.retryable_codes:
                    self._handle_retry(req_id, hostname, policy, retries, response.status_code, duration)
                    retries += 1
                    continue
                    
                if not response.ok:
                    self._log("transport_permanent_error", req_id, hostname, policy.name, status=response.status_code, duration=duration)
                    response.raise_for_status()

                # Verify MIME type matches expectations before handing off to PayloadValidators
                content_type = response.headers.get("Content-Type", "").lower()
                if policy.expected_media != ExpectedMediaType.ANY and policy.expected_media.value not in content_type:
                    self._quarantine(req_id, url, response.text, f"Expected {policy.expected_media.value}, got {content_type}")
                    raise PayloadError(f"[{req_id}] Unexpected content type: {content_type}")

                self._log("transport_success", req_id, hostname, policy.name, status=response.status_code, duration=duration)
                return response
                
            except (Timeout, ConnectionError) as e:
                duration = round(time.time() - start_time, 3)
                self._handle_retry(req_id, hostname, policy, retries, "TIMEOUT_OR_CONN_RESET", duration)
                retries += 1

        self.circuit_breakers[hostname] = time.time() + 60
        self._log("transport_circuit_tripped", req_id, hostname, policy.name)
        raise TransportError(f"[{req_id}] Max retries exceeded for {hostname}")

    def _handle_retry(self, req_id, hostname, policy, attempt, status, duration):
        sleep_time = (policy.base_backoff * (2 ** attempt)) + random.uniform(0.1, 1.0)
        self._log("transport_retry", req_id, hostname, policy.name, attempt=attempt, status=status, delay=round(sleep_time, 2), duration=duration)
        time.sleep(sleep_time)
        
    def _quarantine(self, req_id, url, raw_content, reason):
        filepath = os.path.join(self.quarantine_dir, f"{req_id}.txt")
        meta = {"req_id": req_id, "url": url, "reason": reason, "timestamp": datetime.now().isoformat()}
        with open(filepath, 'w') as f:
            f.write(json.dumps(meta) + "\n\n=== RAW PAYLOAD ===\n" + raw_content)
        self._log("payload_quarantined", req_id, "localhost", "SYSTEM", reason=reason, file=filepath)

    def _log(self, event, req_id, host, policy_name, **kwargs):
        record = {"event": event, "req_id": req_id, "host": host, "policy": policy_name}
        record.update(kwargs)
        print(json.dumps(record))
