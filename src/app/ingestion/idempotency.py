import sqlite3
import threading
import hashlib
import logging

class IdempotencyService:
    """Persistent gatekeeper to prevent duplicate ingestion of SEC filings or events."""
    
    def __init__(self, db_path: str = "ssr_idempotency.sqlite"):
        self.db_path = db_path
        self.lock = threading.Lock()
        self.logger = logging.getLogger("SSR.Idempotency")
        self._init_db()

    def _init_db(self):
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS processed_events (
                        source_id TEXT,
                        content_hash TEXT,
                        processed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (source_id, content_hash)
                    )
                """)

    def is_novel(self, source_id: str, raw_content: str) -> bool:
        """
        Checks if the exact payload has been processed before.
        Automatically marks it as processed if it is novel.
        """
        content_hash = hashlib.sha256(raw_content.encode('utf-8')).hexdigest()
        
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT 1 FROM processed_events WHERE source_id = ? AND content_hash = ?", 
                    (source_id, content_hash)
                )
                if cursor.fetchone():
                    return False
                
                # If it's novel, immediately lock it in to prevent race conditions on the next tick
                conn.execute(
                    "INSERT INTO processed_events (source_id, content_hash) VALUES (?, ?)",
                    (source_id, content_hash)
                )
                return True
