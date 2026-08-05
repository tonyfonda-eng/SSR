# Architecture Repair Report

## 1. Removed Compatibility Shims
- Removed the dynamic `__getattr__` catch-all hook from `src/database.py` that was silently masking missing method calls and table lookups.
- Replaced stubbed persistence calls with concrete SQLite implementation handlers (`workflow_health`, `articles_cache`, `tracked_companies`, `events_log`).

## 2. Migrated Imports & AI Pipeline Fixes
- Restored `_generate_with_retry` inside `src/ai.py` to bridge `src/issuer.py` and `monitor.py` directly to OpenRouter cooldown pools and Gemini round-robin rotation.
- Eliminated all silent warnings during module import.

## 3. Database Standardization
- Unified all persistence onto the canonical SQLite database path: `ssr_observability.db`.
- Verified idempotent schema creation and automated PRAGMA column migrations.
