import sqlite3
import threading
import logging
from datetime import datetime

class NotificationAuditStore:
    """SQLite-backed persistent log for tracking alert states, attempts, and failures."""
    
    def __init__(self, db_path: str = "ssr_notifications.sqlite"):
        self.db_path = db_path
        self.lock = threading.Lock()
        self.logger = logging.getLogger("SSR.NotificationAudit")
        self._init_db()

    def _init_db(self):
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS notification_audit (
                        id TEXT PRIMARY KEY,
                        ticker TEXT,
                        channel TEXT,
                        payload TEXT,
                        status TEXT,
                        attempts INTEGER DEFAULT 0,
                        last_error TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)

    def log_alert(self, alert_id: str, ticker: str, channel: str, payload: str):
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO notification_audit (id, ticker, channel, payload, status)
                    VALUES (?, ?, ?, ?, 'ENQUEUED')
                """, (alert_id, ticker, channel, payload))

    def update_status(self, alert_id: str, status: str, attempts: int, last_error: str = None):
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE notification_audit 
                    SET status = ?, attempts = ?, last_error = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (status, attempts, last_error, alert_id))
