import os
import hashlib
import logging
import time
from datetime import datetime
from src.engine.primitives import ArtifactReference

class DocumentStore:
    """Manages raw cache directories, filesystem isolation, and immutable storage tracks."""
    
    def __init__(self, base_dir: str = "ssr_cache"):
        self.base_dir = base_dir
        self.sec_dir = os.path.join(base_dir, "sec")
        self.market_dir = os.path.join(base_dir, "market")
        self.quarantine_dir = os.path.join(base_dir, "quarantine")
        self.dlq_dir = os.path.join(base_dir, "dlq")
        self.logger = logging.getLogger("SSR.DocumentStore")
        self._ensure_layout()

    def _ensure_layout(self):
        for path in [self.sec_dir, self.market_dir, self.quarantine_dir, self.dlq_dir]:
            os.makedirs(path, exist_ok=True)

    def store_market_payload(self, provider: str, data_type: str, ticker: str, payload: str) -> ArtifactReference:
        """Stores a market data packet as an immutable file and returns an ArtifactReference claim ticket."""
        now = datetime.utcnow()
        year, month, day = now.strftime("%Y"), now.strftime("%m"), now.strftime("%d")
        
        target_dir = os.path.join(self.market_dir, provider.lower(), year, month, day, ticker, data_type.lower())
        os.makedirs(target_dir, exist_ok=True)
        
        payload_bytes = payload.encode('utf-8')
        sha256_hash = hashlib.sha256(payload_bytes).hexdigest()
        size_bytes = len(payload_bytes)
        timestamp_float = time.time()
        
        file_name = f"{now.strftime('%Y%m%dT%H%M%SZ')}_{sha256_hash[:8]}.json"
        full_file_path = os.path.join(target_dir, file_name)
        
        with open(full_file_path, "w", encoding="utf-8") as f:
            f.write(payload)
            
        self.logger.info(f"Immutable market transaction block written to cache: {full_file_path}")
        
        return ArtifactReference(
            provider=provider.upper(),
            data_type=data_type.upper(),
            ticker=ticker,
            cache_path=full_file_path,
            sha256_hash=sha256_hash,
            timestamp=timestamp_float,
            size_bytes=size_bytes
        )

    def read_payload(self, cache_path: str) -> str:
        """Fulfills a Claim Check by reading the immutable payload from disk."""
        if not os.path.exists(cache_path):
            raise FileNotFoundError(f"Artifact referenced by claim check missing from disk: {cache_path}")
        with open(cache_path, "r", encoding="utf-8") as f:
            return f.read()

    def quarantine_payload(self, source: str, payload: str, reason: str):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"QUARANTINE_{source}_{timestamp}.txt"
        target_path = os.path.join(self.quarantine_dir, file_name)
        
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(f"REASON: {reason}\n---\n{payload}")
        self.logger.warning(f"Payload isolated to quarantine storage tier: {target_path}")

    def store_sec_filing(self, accession: str, payload: str):
        """Stores a live SEC filing and returns an ArtifactReference claim ticket."""
        import os, time, hashlib
        from datetime import datetime
        from src.engine.primitives import ArtifactReference
        
        now = datetime.utcnow()
        year, month = now.strftime("%Y"), now.strftime("%m")
        
        # Fallback to local cache dir if self.sec_dir isn't defined
        base_dir = getattr(self, 'sec_dir', 'ssr_cache/sec')
        target_dir = os.path.join(base_dir, year, month)
        os.makedirs(target_dir, exist_ok=True)
        
        payload_bytes = payload.encode('utf-8')
        sha256_hash = hashlib.sha256(payload_bytes).hexdigest()
        
        file_name = f"accession-number={accession}_{sha256_hash[:6]}.html"
        full_file_path = os.path.join(target_dir, file_name)
        
        with open(full_file_path, "w", encoding="utf-8") as f:
            f.write(payload)
            
        if hasattr(self, 'logger'):
            self.logger.info(f"Immutable SEC filing block written to cache: {full_file_path}")
            
        return ArtifactReference(
            schema_version="1.0",
            provider="SEC",
            data_type="FILING",
            ticker="UNKNOWN",
            cache_path=full_file_path,
            sha256_hash=sha256_hash,
            timestamp=time.time(),
            size_bytes=len(payload_bytes)
        )
