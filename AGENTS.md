# AI Agent Instructions for Special Situations Radar

## Purpose
Help AI coding agents understand the repository structure, the external APIs in use, and the simplest commands to run or test the project.

## Project summary
This repository is a Python-based research engine for identifying announced future cash events from news sources. It reads RSS feeds and scrapes news wire HTML, applies rule-based analysis from Google Sheets, and uses Google Gemini for event scoring and reasoning.

## API-related responsibilities
- `src/ai.py` integrates with Google Gemini via the `google-genai` SDK using `genai.Client(api_key=k)` and calls `client.models.generate_content(model='gemini-flash-latest', ...)`.
- API keys are loaded from `GEMINI_API_KEY` (comma-separated) and `GEMINI_API_KEY_1` through `GEMINI_API_KEY_10` environment variables.
- `src/sheets.py` and `tests/test_sheets.py` use the Google Sheets API via `gspread` and service account credentials from `GOOGLE_SERVICE_ACCOUNT_JSON`.
- `src/scrapers/` contains per-source HTML scrapers (BusinessWire, GlobeNewswire, PR Newswire, SEC EDGAR, KEDM) that subclass `src/scrapers/base.py:SourceScraper`.
- `src/rss.py` parses `src.config.RSS_FEED` using `feedparser` (legacy, not used in active pipeline).
- `monitor.py` loads rules from a Google Sheet and drives the full pipeline.

## Important files
- `monitor.py` — main runner that loads Google Sheets rules and drives the pipeline.
- `src/ai.py` — Google Gemini integration and prompt handling.
- `src/sheets.py` — Google Sheets loading logic.
- `src/scrapers/` — Per-source scraper modules (all subclass `SourceScraper`).
- `src/rules_engine.py` — Evidence-scoring rules engine for cash event detection.
- `src/database.py` — SQLite schema initialization and upgrade logic.
- `src/options_calc.py` — Naked call ROI calculator using yfinance.
- `src/alerts/email.py` — Email alert delivery via SMTP.
- `tests/test_sheets.py` — Google Sheets test example and expected runtime environment.
- `.github/workflows/monitor.yml` — CI workflow for running `monitor.py` every 5 minutes.
- `.github/workflows/tests.yml` — repository test workflow.

## Environment and runtime
- Uses Python 3.11 in GitHub workflows.
- Install dependencies with:
  ```bash
  python -m pip install --upgrade pip
  pip install -r requirements.txt
  ```
- Required environment variables:
  - `GEMINI_API_KEY` (and optionally `GEMINI_API_KEY_1` through `GEMINI_API_KEY_10`) for Gemini AI calls.
  - `GOOGLE_SERVICE_ACCOUNT_JSON` for Google Sheets authentication.
  - `SMTP_SERVER`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `ALERT_EMAIL_RECIPIENT` for email alerts.
  - `KEDM_USER`, `KEDM_PASS` for KEDM scraper authentication (optional, scraper skips if unset).
- `tests/test_sheets.py` expects access to `GOOGLE_SERVICE_ACCOUNT_JSON` and a live Google Sheet URL.

## How to run and test
- Run the monitor flow: `python monitor.py`
- Run the sheet integration test: `python tests/test_sheets.py`

## Agent behavior guidance
- The repo does not contain a web server or HTTP API service.
- When asked about "API" in this codebase, interpret it as external service APIs: Google Gemini, Google Sheets, and news source scrapers.
- Avoid inventing missing implementation details. Prefer using existing code and workflows.
- Link to `ARCHITECTURE.md` if a higher-level architectural explanation is needed.

## Notes
- `src/config/settings.py` defines the RSS feed and other static settings.
- `src/config/secrets.py` reads Google credential JSON from environment.
- This project is experimental and small; keep changes minimal and consistent with the existing lightweight Python style.
