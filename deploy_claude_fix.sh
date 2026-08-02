#!/bin/bash
set -e

echo "📦 Step 1: Navigating to project workspace..."
cd ~/special-situations-radar-main

echo "🧠 Step 2: Writing optimized src/ai.py (Cooldown Pool & Round-Robin)..."
cat << 'PYTHON_EOF' > src/ai.py
import os
import time
import logging

logger = logging.getLogger(__name__)

# Scraper classification tasks require efficient, short outputs to stay within free tier limits
MAX_TOKENS = 1024
COOLDOWN_SECONDS = 300  # 5-minute backoff on 402/rate-limit errors instead of permanent removal

class OpenRouterPool:
    def __init__(self):
        raw_keys = [os.environ.get("OPENROUTER_API_KEY", "")]
        for i in range(1, 8):
            raw_keys.append(os.environ.get(f"OPENROUTER_API_KEY_{i}", ""))
        
        # Filter out blank or whitespace-only keys
        self.keys = [k.strip() for k in raw_keys if k and k.strip()]
        self.cooldowns = {}  # key -> timestamp when it can be retried
        logger.info(f"[AI INFO] Initialized OpenRouter pool with {len(self.keys)} active keys.")

    def get_available_key(self):
        now = time.time()
        for key in self.keys:
            if self.cooldowns.get(key, 0) < now:
                return key
        return None  # All keys currently in cooldown

    def mark_cooldown(self, key):
        self.cooldowns[key] = time.time() + COOLDOWN_SECONDS
        logger.warning(f"[AI RETRY] OpenRouter key placed on cooldown for {COOLDOWN_SECONDS}s.")

class GeminiPool:
    def __init__(self):
        raw_keys = [os.environ.get("GEMINI_API_KEY", "")]
        for i in range(1, 8):
            raw_keys.append(os.environ.get(f"GEMINI_API_KEY_{i}", ""))
        
        # Filter out blank or whitespace-only keys to prevent ghost slots
        self.keys = [k.strip() for k in raw_keys if k and k.strip()]
        self._index = 0
        logger.info(f"[AI INFO] Initialized Gemini pool with {len(self.keys)} active keys.")

    def next_key(self):
        if not self.keys:
            return None
        # True round-robin load distribution via modulo indexing
        key = self.keys[self._index % len(self.keys)]
        self._index += 1
        return key

# Global singleton client pools
or_pool = OpenRouterPool()
gemini_pool = GeminiPool()
PYTHON_EOF

echo "🗄️ Step 3: Writing optimized src/database.py (Defensive Schema Migration)..."
cat << 'PYTHON_EOF' > src/database.py
import sqlite3
import os
import logging

logger = logging.getLogger(__name__)

DB_PATH = "ssr_observability.db"

def ensure_columns(conn, table, columns):
    """Safely inspect existing table schema via PRAGMA and add missing columns dynamically."""
    try:
        cursor = conn.execute(f"PRAGMA table_info({table})")
        existing = {row[1] for row in cursor.fetchall()}
        for col_name, col_type in columns.items():
            if col_name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type} DEFAULT 0")
                logger.info(f"[DATABASE MIGRATION] Added missing column '{col_name}' to table '{table}'.")
        conn.commit()
    except Exception as e:
        logger.error(f"[DATABASE MIGRATION ERROR] Failed to update schema for {table}: {e}")

def init_db():
    """Ensures all core SQLite database tables and telemetry columns are fully provisioned."""
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    
    # Base table definitions
    conn.execute("""
        CREATE TABLE IF NOT EXISTS workflow_health (
            timestamp TEXT PRIMARY KEY,
            total_scanned INTEGER,
            articles INTEGER,
            errors INTEGER,
            drift_score REAL,
            runtime REAL
        );
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS run_metrics_log (
            timestamp TEXT PRIMARY KEY
        );
    """)
    
    conn.commit()

    # Dynamic schema auto-migration for telemetry attributes
    ensure_columns(conn, "workflow_health", {
        "failed": "INTEGER",
        "succeeded": "INTEGER",
        "skipped": "INTEGER"
    })
    
    conn.close()
    logger.info("[DATABASE] Ready and fully migrated.")
PYTHON_EOF

echo "🚀 Step 4: Staging, committing, and pushing architecture refactor..."
git add src/ai.py src/database.py
git commit -m "refactor(core): implement claude's cool-down pool, secret filtering, round-robin, and pragma migrations"
git pull --rebase origin main
git push origin main

echo "✅ Claude's architecture fix deployed successfully!"
