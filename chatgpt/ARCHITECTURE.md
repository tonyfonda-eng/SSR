# SSR Technical Architecture

This document defines the underlying execution environment and system modules that power the Special Situations Radar (SSR).

## Core Stack & Environment
- **Language:** Python 3.11
- **Deployment:** GitHub Actions (serverless cron jobs triggering `monitor.py`).
- **Dependencies:** `beautifulsoup4`, `feedparser`, `requests`, `gspread`, `google-auth`, `google-genai`.
- **Secrets:** `GEMINI_API_KEY` (comma-separated list for rotation), `GOOGLE_SERVICE_ACCOUNT_JSON` (for gspread auth), `SMTP_*` variables for email.

## System Modules
- **`monitor.py`:** The primary orchestrator. Loops over sources, handles pre-filtering (Regex & Global Exclusions), triggers the Rules Engine, interrogates the AI, and manages database state.
- **`src/sheets.py`:** The control plane interface. Uses `gspread` to read Rules, Playbooks, Exclusions, and Sources from the Google Sheet. Also writes back to the "AI Research Queue".
- **`src/rules_engine.py`:** The dumb filter. Scores article text against keywords and confidence modifiers. Natively generates the `evidence_log` and `confidence` score.
- **`src/ai.py`:** The Research Engine. Implements a client pool for Gemini API key rotation to bypass free-tier rate limits. Exposes three strict functions: `classify_event` (intent), `extract_target_ticker` (target isolation), and `execute_playbook` (12-section structured Investment Memo).
- **`src/database.py`:** The Knowledge Base (SQLite). Maintains relational state across runs. 
  - `articles`: Raw ingestion cache to prevent rescraping.
  - `events`: Deduplication state. Uses primary key `EventFamily_Ticker_YYYY_MM`.
  - `companies`: Tracks historical alert counts per ticker.
  - `research_logs`: Permanently logs AI memos and Rules scores for strategy analytics.
- **`src/alerts/email.py`:** The alerting interface. Deterministically stitches the Python-generated Evidence Log (Section 3) into the middle of the AI-generated Markdown memo to prevent hallucination of keyword matches.

## Critical Execution Flows
1. **Ticker Extraction & Deduplication:** AI extracts the target ticker. If it returns `"PRIVATE"`, `monitor.py` drops the article. If public, it calls `create_event_if_new(event_family, ticker)`. If this returns `None`, the event is a duplicate (e.g. syndicated news) and the article is dropped.
2. **Regex Pre-Filtering:** PR Newswire/GlobeNewswire bodies are scanned using a massive compiled regex list of global stock exchange acronyms. If `len(matches) == 0`, the article is instantly dropped before reaching the rules engine. (This check is bypassed for SEC EDGAR).
