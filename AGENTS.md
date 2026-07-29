# AI Agent Instructions for Special Situations Radar

## Purpose
Help AI coding agents understand the repository structure, the external APIs in use, and the simplest commands to run or test the project.

## Project summary
This repository is a Python-based research engine for identifying announced future cash events from news sources. It reads RSS feeds, applies rule-based analysis from Google Sheets, and uses OpenAI for event scoring and reasoning.

## API-related responsibilities
- `src/ai.py` integrates with the OpenAI Python SDK using `OpenAI(api_key=os.environ["OPENAI_API_KEY"])` and calls `client.responses.create(...)`.
- `src/sheets.py` and `tests/test_sheets.py` use the Google Sheets API via `gspread` and service account credentials from `GOOGLE_SERVICE_ACCOUNT_JSON`.
- `src/rss.py` parses `src.config.RSS_FEED` using `feedparser`.
- `monitor.py` loads rules from a Google Sheet and prints them.

## Important files
- `monitor.py` — main runner that loads Google Sheets rules and uses the app logic.
- `src/ai.py` — OpenAI integration and prompt handling.
- `src/sheets.py` — Google Sheets loading logic.
- `src/rss.py` — RSS feed parsing.
- `src/database.py` — SQLite schema initialization and upgrade logic.
- `tests/test_sheets.py` — Google Sheets test example and expected runtime environment.
- `.github/workflows/tests.yml` — repository test workflow.
- `.github/workflows/monitor.yml` — CI workflow for running `monitor.py`.

## Environment and runtime
- Uses Python 3.11 in GitHub workflows.
- Install dependencies with:
  ```bash
  python -m pip install --upgrade pip
  pip install -r requirements.txt
  ```
- Required environment variables:
  - `OPENAI_API_KEY` for OpenAI calls.
  - `GOOGLE_SERVICE_ACCOUNT_JSON` for Google Sheets authentication.
- `tests/test_sheets.py` expects access to `GOOGLE_SERVICE_ACCOUNT_JSON` and a live Google Sheet URL.

## How to run and test
- Run the monitor flow: `python monitor.py`
- Run the sheet integration test: `python tests/test_sheets.py`

## Agent behavior guidance
- The repo does not contain a web server or HTTP API service.
- When asked about "API" in this codebase, interpret it as external service APIs: OpenAI, Google Sheets, and RSS feed consumption.
- Avoid inventing missing implementation details. Prefer using existing code and workflows.
- Link to `ARCHITECTURE.md` if a higher-level architectural explanation is needed.

## Notes
- `src/config/settings.py` defines the RSS feed and other static settings.
- `src/config/secrets.py` reads Google credential JSON from environment.
- This project is experimental and small; keep changes minimal and consistent with the existing lightweight Python style.
