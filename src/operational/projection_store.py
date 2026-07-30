import sqlite3
import json
import threading
import logging
from typing import List, Dict

class ProjectionStore:
    """SQLite-backed Key-Value store for maintaining materialized view states."""
    
    def __init__(self, db_path: str = "ssr_projections.sqlite"):
        self.db_path = db_path
        self.lock = threading.Lock()
        self.logger = logging.getLogger("SSR.ProjectionStore")
        self._init_db()

    def _init_db(self):
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS projection_rows (
                        sheet_name TEXT,
                        row_id TEXT,
                        data_json TEXT,
                        is_dirty INTEGER DEFAULT 1,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (sheet_name, row_id)
                    )
                """)
                try:
                    conn.execute("CREATE INDEX idx_dirty ON projection_rows(sheet_name, is_dirty)")
                except sqlite3.OperationalError:
                    pass  # Index already exists

    def apply_event(self, sheet_name: str, row_id: str, payload_dict: dict):
        """Upserts a row into the projection store and marks the sheet as dirty."""
        data_json = json.dumps(payload_dict)
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO projection_rows (sheet_name, row_id, data_json, is_dirty, updated_at)
                    VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
                    ON CONFLICT(sheet_name, row_id) DO UPDATE SET
                        data_json = excluded.data_json,
                        is_dirty = 1,
                        updated_at = CURRENT_TIMESTAMP
                """, (sheet_name, row_id, data_json))

    def get_dirty_sheets(self) -> List[str]:
        """Returns a list of sheet names that have pending mutations."""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT DISTINCT sheet_name FROM projection_rows WHERE is_dirty = 1")
                return [row[0] for row in cursor.fetchall()]

    def get_sheet_rows(self, sheet_name: str) -> List[Dict]:
        """Retrieves all rows for a given sheet as parsed dictionaries."""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT data_json FROM projection_rows WHERE sheet_name = ?", (sheet_name,))
                return [json.loads(row[0]) for row in cursor.fetchall()]

    def clear_dirty_token(self, sheet_name: str):
        """Marks all rows in a sheet as clean (synchronized)."""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("UPDATE projection_rows SET is_dirty = 0 WHERE sheet_name = ?", (sheet_name,))
