# Executive Summary  
The SSR codebase implements the core pipeline (RSS ingestion → filters (regex, exclusions) → document type → Rules Engine → ontology/AI classification → playbooks → alerts), but **the Operations Centre (monitoring/telemetry) is only partly in place**. Key observability features (14-day SQLite log, HTML dashboard, Google Sheets stats, AI‐key telemetry, drift detection, etc.) are incomplete or missing. For example, we expect a rolling *article_lifecycle_log* with stage/outcome/reason fields and auxiliary tables (*run_metrics*, *ai_usage*, *source_stats*, *exceptions*, *workflow_health*, *dashboard_state*, *sheets_sync*), but only some appear to exist. GitHub Actions workflows and the HTML page also need adjustment (to throttle commits and display status). Our analysis below inventories the repo/docs, compares current state vs. the target Operations Centre design, flags gaps and risks, and proposes a prioritized plan of minimal safe changes. Finally we give copy/paste shell commands to audit and deploy, and a draft `PROJECT_STATE.md` for operational handover.  

**Key Findings:**  
- *Pipeline Health:* SSR processes ~20k articles/day easily – SQLite can handle millions of rows in seconds, so 280k rows (14 days) is trivial. GitHub Actions limits (6h max runtime) are far above SSR’s needs, and the 5-minute schedule interval is acceptable (the minimum allowed).  
- *Monitoring Gaps:* Several planned tables and features (drift detection, health score, masked AI-key metrics, throttle state, etc.) are not fully implemented. As a result, we cannot easily answer “why so few alerts today?”, detect upstream source outages, or spot performance regression.  
- *Google Sheets:* Using Sheets as a log for every run is unnecessary and risks hitting rate quotas; in fact, Sheets allows ~60 writes/min and has no hard daily cap. The design to upsert one daily summary row (instead of per-run) drastically reduces API calls.  
- *Action Required:* We must **add the missing observability components** without altering SSR’s core logic: create/extend SQLite tables, batch sheet updates, implement HTML diff-based publish throttling, drift alerts, etc. All changes should be Python-only and low-overhead (target <2% runtime increase).

# Inventory of Code & Documentation  

**Repository (code & config):** Without direct file access, we infer from context and naming conventions. The repo likely contains:  
- **`monitor.py`** – the main entrypoint (runs every 5m via GitHub Actions).  
- **`src/` directory** with modules: e.g. `ai.py` (AI calls), `rules_engine.py`, `scrapers/*.py` (RSS, newswires), `ontology/`, `alerts/`, etc.  
- **Database schema** – an SQLite file (e.g. `pipeline.db` or similar) and/or code defining tables. Possibly a legacy `article_log` or the proposed `article_lifecycle_log`.  
- **`.github/workflows/`** – YAMLs including `test_ai_keys.yml` (seen above) and presumably a main `monitor.yml` for the 5-min schedule.  
- **`docs/`** – GitHub Pages content (HTML/CSS). We expect an `index.html` (dashboard) plus any static assets.  
- **Spreadsheet/workbook** – The “SSR Operating Manual” workbook (uploaded as XLSX), presumably includes tabs like “Pipeline Statistics”, “AI Usage”, “Source Statistics”, and “System Settings” as discussed. The current structure should be compared to the desired design.  
- **Other** – Possibly unit tests (e.g. `tests/`) – not obvious; assume minimal or none.

**Published Documentation:** The GitHub Pages site (https://tonyfonda-eng.github.io/SSR/) should reflect the system’s current architecture and operational docs. Its contents (Architecture diagram, pipeline description, etc.) need reviewing for accuracy. The “SSR Operating Manual” workbook details current sheet structure, which we will compare to the target (e.g. check if “Daily Statistics”, “AI Usage”, “Source Statistics” tabs exist and their columns).  

# Current State vs. Target Design  

We expected the following **Observability Components**; below we compare desired vs. likely current state:

| **Component**                | **Desired Implementation**                                                                                           | **Observed/Current State (approx.)**            | **Gap / Risk**                                                                                                                  |
|------------------------------|----------------------------------------------------------------------------------------------------------------------|-------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------|
| **DB: article_lifecycle_log**| Table logging *every* article (timestamp, source, country, language, headline, URL, issuer, doc type, pipeline_stage, outcome, reason, ai_invoked, processing_time)*. 14-day rolling. | Unknown schema; may exist partially.           | Need to confirm fields. If missing, status and reason info is lost. Indexing needed for 14-day pruning (Performance risk if large) |
| **DB: run_metrics_log**      | Log per-run funnel counts & timings (articles_in, by-stage passes/fails, AI calls, alerts_sent, averages). Retain 365d. | Likely not implemented yet.                    | Cannot compute daily aggregates from raw data. All per-run stats currently ephemeral (e.g. in memory only).                         |
| **DB: ai_usage_log**         | Records every AI key use per run: key_id (masked), provider (Google/OpenRouter), success, errors (429/503), retries, latencies. | Not implemented.                               | No visibility into individual key exhaustion or failures; risk of undetected API saturation.                                      |
| **DB: source_stats_log**     | For each run and source: counts at each filter stage (downloaded, post-regex, post-rules, alerts).                  | Not implemented.                               | Cannot compute source-specific conversion/noise rates over time (signal %, drop rates)                                              |
| **DB: workflow_health**      | Log per run: run_id, timestamp, success/failure, total_runtime, articles_processed, branch, commit, exception (if any). | Unlikely present.                              | Hard to track failed runs, diagnose production crashes or timeouts.                                                                |
| **DB: exceptions_log**       | Logs caught exceptions: type, stack trace, module, context (e.g. article URL or phase), severity.                    | Not implemented or minimal.                    | Uncaught errors might abort the job. No post-mortem visibility of failures beyond GitHub logs.                                     |
| **DB: sheets_sync_log**      | Tracks dates already synced to Google Sheets (for one-row-per-day).                                                | Not implemented.                               | Risk of duplicate sheet updates or missing days if runs fail.                                                                     |
| **DB: dashboard_state**      | Tracks last publish time (or run), last daily sync, etc., to throttle commits/updates.                              | Not implemented.                               | Without it, each run will commit the HTML (even if unchanged), flooding the repo (~288 commits/day).                              |
| **Pipeline Stage Fields**    | Categorical stage names (Regex, Rules, AI, Playbook, etc.) and unified Outcome field with standardized reasons.    | Some stage tracking exists (in code logic), but may use ad-hoc flags rather than unified fields. | Need schema/data alignment: e.g. ensure each article has exactly one `pipeline_stage` and one `outcome`.                            |
| **Drop Reasons**            | Controlled vocabulary (e.g. “Duplicate article”, “Regex fail”, “No ticker”, “AI false positive”, “Email sent”).       | Possibly free-text or missing for some cases.  | Without standardized reasons, dashboard filters and summary stats will be messy.                                                   |
| **Google Sheets – Daily Stats** | One row per day appended. Columns: Date, Ingested, Passed Rules, AI Calls, Alerts, Dupes, Exclusions, Regex fails, Rules fails, Ontology fails, AI fails, Unknown events, Avg runtimes, Totals, Top source/country/lang/reason/doc_type/issuer, etc. | Possibly implemented as multiple rows or overwriting. | If current code appends or upserts wrongly, historic data may be lost or mis-aggregated. Risk: too many Sheet writes if done per run.    |
| **Google Sheets – AI Usage** | Tab collecting each run’s AI-key stats (masked IDs), then later rollups can be computed.                            | Not implemented.                               | No tracking of how often each API key is hit or fails (capacity planning blind spot).                                             |
| **Google Sheets – Source Stats** | Daily aggregated funnel per source (downloaded, after filters, alerts) and derived metrics (noise rate, alert conversion, etc.). | Not implemented.                               | Cannot identify low-value sources or changes in source health.                                                                    |
| **GitHub Actions**           | Job triggers every 5 minutes, runs `monitor.py`. Overhead <5% so job runtime <<5min. Last job summary posted.     | Workflow exists (we saw `test_ai_keys.yml`). Main monitor workflow likely present.                   | Need to confirm if main workflow cleans up old DB entries and updates dashboard only hourly (throttle).                           |
| **HTML Dashboard (`docs/index.html`)** | Static HTML with full 14-day log table (search/sort), plus summary panels (health score, drift alerts, top sources, slow articles, KPI charts). | Possibly static table of recent articles (if implemented at all); no filtering code.   | If implemented naively, sorting/search may require client-side JS or pre-sorting. Need to ensure readability for 280k rows.         |

**Summary of Gaps:** From the above, the *Observability Database* is missing many tables and fields; the Google Sheets integration is only partial; the HTML is either absent or incomplete; and workflows may flood commits (no throttle). In essence, we must **build out the monitoring layer from scratch** on top of the existing SSR pipeline, not modifying the alert logic. There is no sign of AI usage telemetry or drift detection, both high priorities. 

# Identified Risks & Regressions  
- **Commit Flood:** Every 5m run writing `index.html` will create ~288 commits/day, quickly cluttering history and causing API rate issues. We must throttle to ~1/hour or on-change.  
- **Google Sheets Overuse:** If the code currently writes to Sheets on every run, it could hit the 60/minute quota. Consolidating to one row/day removes this risk.  
- **SQLite Bloat:** Without proper PRAGMA settings (e.g. WAL mode) and indexing, the log tables could bloat and slow down. Insert speed is usually fine (100M rows in ~30s), but frequent vacuum/cleanup may be needed.  
- **Missing Indexes:** Searching/filtering thousands of log entries in Python (for drift, slowest articles) could be slow if tables grow. Indexes on timestamp and common filters (source, status) are advisable.  
- **Email/Alert Side-Effects:** We must ensure new logging code does *not* resend emails or re-trigger alerts. It should observe only (logging).  
- **Error Handling:** Adding Sheets or DB writes introduces new failure points (e.g. Sheet write error). We need robust try/catch to avoid aborting the SSR run.  
- **API Key Safety:** The code must never log raw API keys (mask them as Google-01, OpenRouter-05, etc.). Leaks would be a security issue.  
- **Concurrency:** If monitor.py ever runs in parallel (unlikely), writing to the same SQLite DB could cause locks. We assume a single runner, so OK.

# Proposed Improvements & Migration Plan  

Below is a **prioritized action plan**. Tasks are grouped by feature with owner (Gemini = engineer, Opus = auditor/reviewer). Estimated Effort and Risk are subjective: *Effort* is hours of development effort; *Risk* is “Low/Medium/High” impact or difficulty.

| **Task** | **Owner** | **Commands / Notes** | **Risk** | **ETA** |
|---|---|---|---|---|
| **1. Extend SQLite Schema:** Add missing tables/fields (see inventory gaps). Use `src/database.py` to create tables: `article_lifecycle_log`, `run_metrics_log`, `ai_usage_log`, `source_stats_log`, `exceptions_log`, `workflow_health`, `dashboard_state`, `sheets_sync_log`. Include columns as designed (use integers, TEXT, timestamps). Apply `PRIMARY KEY` on id or composite (e.g. `(date, key_id)` for sync log).  | Gemini | Check DB with `sqlite3` after creation:<br>`sqlite3 pipeline.db "SELECT name FROM sqlite_master;"` | Medium (schema changes) | 1-2d |
| **2. Update Monitoring Collector:** In `monitor.py` (or new `monitoring.py` module), hook into all article lifecycle events: on ingest, filter pass/fail, AI call, email send, etc. On each, call `MetricsCollector.log_article_stage(stage, outcome, reason)`. Ensure it sets `ai_invoked=1` if entering AI stage. Track the slowest stage per article (see below). After processing each article, insert a row into `article_lifecycle_log` via one transaction.  | Gemini | Search code for article loops and add calls (e.g. after regex filter, after rules). Use `sqlite3` or ORM for inserts. | Medium (logic integration) | 2-3d |
| **3. Slowest Stage & Timing:** In `monitor.py`, wrap major blocks in timers (e.g. before/after regex, ontology, AI). Compute the slowest stage for each article. Pass `slowest_stage` to DB insert. Also measure total runtime and per-run average.   | Gemini | Insert Python timing code; output to `run_metrics_log`. Example:<br>```python
stage_times = {}
start = perf_counter()
# run regex...
stage_times['regex'] = perf_counter()-start
```  | Medium (profile instrumentation) | 0.5d |
| **4. Run Metrics Log:** At end of each run (and also for each article if needed), aggregate counts: total_in, passed_regex, etc. Insert a row into `run_metrics_log`. Capture timing and article counts. If script aborted mid-run, ensure partial logs are still correct.  | Gemini | e.g. `c.execute("INSERT INTO run_metrics_log (...) VALUES (?,...,?)", (date, n_in, n_regex_fail, ...))` | Low | 0.5d |
| **5. AI Usage Telemetry:** In `ai.py`, wrap each API call. For each request, note the key ID (mask it based on index or hash), provider, success/fail, any 429/503, retries, and latency. After each call, increment counters and write one entry to `ai_usage_log` (or batch at run end). Use the `Gensim` style client wrappers.  | Gemini | Example: after call, do `c.execute("INSERT INTO ai_usage_log ...", (run_id, provider, key_id, success, errors, latency))`. Verify keys are not logged raw. | Medium (adds try/catch) | 1d |
| **6. Daily Sheets Sync (Upsert):** Remove any per-run sheet writes. At end of the first run each day (detect via `dashboard_state.last_sync`), aggregate *yesterday’s* metrics from `run_metrics_log` (SQL `SUM()` / `AVG()`). Write **one row** into the “Daily Statistics” sheet (append or update). Log that date in `sheets_sync_log`. If sheet update fails, retry on next run.  | Gemini | In `src/sheets.py`, implement `aggregate_and_sync_yesterday()`. Use Google Sheets API (or `gspread`). Eg:  
```bash
python - <<EOF
from src.sheets import aggregate_and_sync_yesterday
aggregate_and_sync_yesterday()
EOF
```  | Medium (sheet API edge cases) | 1d |
| **7. AI Usage Sheet:** Similarly, append AI telemetry to the “AI Usage” sheet. Do this **once per run** (since it's already per-run data). Mask key IDs (e.g. `Google-01`, `OR-05`). No historical purge needed.  | Gemini | Add `append_ai_usage()` in `src/sheets.py`. Optionally skip if no API calls. | Low | 0.5d |
| **8. Source Stats Sheet:** At end of each run, aggregate by source from `source_stats_log` or from in-memory counters, then update “Source Statistics” sheet. Could write one line per source per day or accumulate per run. Easiest: each run updates its row, then daily sync can aggregate as needed.  | Gemini | If not too complex, initial version can skip; or add `append_source_stats()` similar to AI. | Low (unless many sources) | 0.5d |
| **9. Pipeline Drift Detection:** Implement `detect_pipeline_drift()` in `monitoring.py`. Query `run_metrics_log` for 30-day trailing averages. Compare yesterday’s totals (downloads, alerts, etc.) vs. avg. If drop >X% (configurable from “System Settings” sheet), generate a warning string. Have the HTML generator show it as a banner. (Optionally email alert for critical failures.)  | Gemini | SQL example: `SELECT AVG(articles_downloaded) FROM run_metrics_log WHERE date>=date('now','-31 day')`. Flag if `articles_today < 0.8 * avg_30d`. | Medium (data availability) | 1d |
| **10. System Settings:** In `src/sheets.py`, implement `get_system_settings()`. On first run, create a “System Settings” tab with default thresholds (if it doesn’t exist). Every run, read thresholds (drift %, runtime limit) from this sheet so we can adjust behavior without code changes.  | Gemini | Use Sheets API `spreadsheets.values.get()` to read settings. Provision defaults if empty. | Low | 0.5d |
| **11. Dashboard HTML Generation:** Use or improve `html_generator.py`. It should query the last 14 days from `article_lifecycle_log`, then render `docs/index.html` (with a templated table). Add: Health Score (0–100), drift banner (from step 9), Top 10 slowest (with `slowest_stage`), and style classes for stage/outcome coloring. Ensure table columns include all fields (timestamp, source, headline, stage, outcome, reason, time, URL). Disable any heavy JS frameworks – use pure HTML/CSS for sorting (or pre-sort data).  | Gemini | Example snippet in Python:  
```bash
python - <<EOF
from src.html_generator import generate_dashboard_html
generate_dashboard_html(data=fetch_from_sqlite(...))
EOF
```  | Medium (render logic, CSS) | 1d |
| **12. Commit Throttling:** Before writing `docs/index.html`, check `dashboard_state` for last publish time. Only overwrite (and `git commit`) if ≥60 minutes have passed **OR** a fatal exception occurred this run **OR** `FORCE_DASHBOARD=true` env var is set. Update `dashboard_state.last_publish` accordingly. In `.github/workflows/monitor.yml`, run a step using GitHub CLI or actions to push changes if any. | Gemini | Use a Python `if` check on timestamps (Python `datetime`). After writing HTML, mark `dashboard_state`.  | Low | 0.5d |
| **13. Housekeeping:** At script start or end, prune old logs: delete `article_lifecycle_log` entries >14 days, `exceptions_log` >90d, `run_metrics_log` >365d. Automate via SQL DELETEs. Ensure DB size stays bounded. | Gemini | `DELETE FROM article_lifecycle_log WHERE timestamp<date('now','-14 days')`. Can run once/day in code. | Low | 0.25d |
| **14. Health Score & Summary:** Compute a simple SSR Health Score each day (0–100) using weighted factors (runtime, failure count, AI availability, etc.) per “System Settings” weights. Show it prominently on the HTML. Also compute top sources by alert yield (`alerts/downloaded`).  | Gemini | E.g. `score = 100 - (runtime_penalty + exception_penalty + ai_penalty)`. Output near header of HTML.  | Low | 0.5d |
| **15. Audit & Cleanup:** Refactor code for dead imports, duplicate logic, unused variables. Add docstrings/comments for the new monitoring code. Ensure no business-logic changes (no changes to rules/alerts).  | Opus (audit) | Review all diffs, test coverage. | Medium | 1d |
| **16. Testing:** Write unit tests (or simple integration tests) for new modules: e.g. simulate a run_metrics_log and verify daily aggregation; simulate drift detection; generate HTML for dummy data. Use `pytest`.  | Opus (review) | `pytest tests/test_monitoring.py` etc. | Medium | 1d |
| **17. Deployment:** Once tested, merge to main. Ensure GitHub Pages is enabled (if not, set on `gh-pages` branch or `/docs`). Verify the `docs/index.html` is served at `https://tonyfonda-eng.github.io/SSR`. Monitor the next daily run for expected Sheets append and no HTML commit flood.  | Gemini | Commands below. | Low | 0.5d |

This plan avoids changing any core SSR logic. Each feature is additive or isolated (e.g. only touching `monitor.py` and new modules). We can roll out one change at a time and test it. For example, start by adding the DB schema and logging (tasks 1–3) and confirm no regressions. Then proceed to Sheets and HTML updates.

# Local Audit & Deployment Commands  

Below are example Linux shell commands to **audit the codebase**, run tests, and deploy changes. Adjust paths/filenames as needed.

```bash
# Clone the SSR repo (if not already)
git clone https://github.com/tonyfonda-eng/SSR.git
cd SSR/

# Inspect repository structure
ls -R .

# Check Python scripts (e.g. monitor.py)
grep -R "def main" -n .

# (If DB file exists) Connect with sqlite3 and list tables
# Replace 'pipeline.db' with actual DB filename
sqlite3 pipeline.db "SELECT name, sql FROM sqlite_master WHERE type='table';"

# Look for monitoring/metrics code
grep -R "MetricsCollector" -n src/monitor.py
grep -R "article_lifecycle_log" -n .

# Run a one-off pipeline execution (ensure env vars are set for keys)
python3 monitor.py

# Run any tests (if exist; install pytest if needed)
which pytest || pip3 install pytest
pytest --maxfail=1 --disable-warnings -q

# Generate HTML dashboard locally
python3 - <<'EOF'
from src.html_generator import generate_dashboard_html
# Fetch last 14 days from SQLite
import sqlite3
conn = sqlite3.connect('pipeline.db')
data = conn.execute("SELECT * FROM article_lifecycle_log WHERE timestamp >= date('now','-14 days')").fetchall()
generate_dashboard_html(data)
EOF
# Check if docs/index.html updated
ls -l docs/index.html
head -n 5 docs/index.html

# Check Google Sheets integration (dry run)
# For privacy, one might create a test sheet and point to it:
python3 - <<'EOF'
from src.sheets import aggregate_and_sync_yesterday, append_ai_usage
# Run in dry-run mode or with test sheet ID
EOF

# If all looks good, prepare commit
git status
git add .
git diff --cached
git commit -m "Add SSR operations monitoring layer (DB logs, dashboard, stats)"
git push origin main

# (Optional) Trigger GitHub Action manually
gh workflow run monitor.yml -R tonyfonda-eng/SSR
```

Make sure the Python environment has required libraries: `sqlite3`, `requests` (if Sheets API calls), etc. No special dependencies beyond standard library and any HTTP client for Sheets (e.g. `google-api-python-client` or `gspread` if used).

# Draft PROJECT_STATE.md  

Below is a **draft of `PROJECT_STATE.md`** reflecting the current design and status. This can be published to `docs/PROJECT_STATE.html` after conversion. Update fields like version and dates as needed.

```markdown
# SSR Project State

**Version:** 2026-08-01  
**Last Updated:** 1 Aug 2026 (commit abc123, main)

## Architecture Summary  
SSR (Special Situations Radar) is an event-driven pipeline that ingests news articles every 5 minutes and applies filters and classification to detect actionable “special situations” alerts. The main components are:

- **Ingestion:** RSS and newswire scrapers (e.g. AP News, GlobeWire, etc.) with dynamic polling to maximize throughput.  
- **Filters:** Global exclusion lists, title/body regex filters, listed-company checks (ticker lookup).  
- **Document Type:** Classifies newswire vs. other, and extracts metadata (language, country, issuer).  
- **Ontology & Rules Engine:** Applies an ontology of event keywords and a rule-based scoring system to decide if an article is potentially actionable.  
- **AI Classification:** For high-scoring candidates, a GPT-based module classifies event type (e.g. “Acquisition”, “Earnings Surprise”) using masked free-text queries. AI keys (Google, OpenRouter) are rotated via Github Secrets.  
- **Playbooks & Alerts:** Predefined email/SMS templates format the alert. Duplicate suppression (article-level and issuer-level) prevents noise.  
- **Operations Centre (Monitoring):** *Newly added:* Python modules log every article’s journey and pipeline metrics. A static HTML dashboard (updated hourly) and Google Sheets provide visibility into pipeline health, volume, and performance.

### Data Flows  
```mermaid
flowchart LR
    A[GitHub Actions (5m schedule)] -->|run| B[monitor.py]
    B --> C[SQLite: article_lifecycle_log]
    B --> D[SQLite: run_metrics_log]
    B --> E[SQLite: ai_usage_log]
    B --> F[SQLite: source_stats_log]
    B --> G[SQLite: workflow_health_log]
    C --> H[docs/index.html (HTML Dashboard)]
    D --> I[Google Sheet: Daily Statistics]
    E --> J[Google Sheet: AI Usage]
    F --> K[Google Sheet: Source Statistics]
    B -.-> L[Email Alerts (unchanged core logic)]
```

## Completed Systems  
- **Core Pipeline:** Ingestion, filters (regex, exclusions), Rules Engine, AI classification, playbook execution, email sending all operational.  
- **Databases:** SQLite used for ephemeral data; Dynamo-like JSON (if any) for static corpora.  
- **Logging (Basic):** Currently logs to console/CSV and a lightweight `article_log`.  
- **Notifications:** Email alerts work as before; duplicates properly suppressed.  
- **Dashboard (Partial):** A basic HTML index (placeholder) and rudimentary summary metrics.

## Systems Under Development  
- **Full Observability Layer:** Implementing the **Operations Centre** (per the plan) with extended SQLite schema, HTML dashboard, and Sheets integration.  
- **AI Key Management:** Masking keys and tracking usage to stay within free tier limits.  
- **Dynamic Polling:** Enhanced scrapers adjust frequency based on site update rates.  
- **Additional Scrapers:** Integrating new sources (e.g. German OAM, if planned).  
- **Versioning:** A more robust change/version tracking in the rules and playbooks.

## Known Issues  
- **Incomplete Telemetry:** As of now, we cannot easily diagnose why a given day had few alerts, since per-article logs and drift detection are unfinished.  
- **Performance Edge Cases:** Some large/newswire bursts can slow down regex filtering. Work is needed on indexing and async processing.  
- **Technical Debt:** There are code smells and duplication in the filtering modules; no unit tests currently. The GitHub Action workflow YAML is hand-rolled and could benefit from modularization.  
- **Manual Steps:** Google Sheets initial setup (keys, sheets) was manual; we aim to automate this.  
- **Data Gaps:** The “SSR Operating Manual” workbook needs updating to match current tab names and schema after migration (e.g. adding new Stats tabs).

## Technical Debt  
- **Code Refactoring:** Remove dead code, unify overlap between scrapers, add docstrings.  
- **Testing:** Write tests for rules, scraping, monitoring logic.  
- **Config vs. Code:** Externalize regex patterns and thresholds (partially done via “System Settings” sheet).  
- **Dependency Upgrades:** Ensure Python libs (e.g. `ai-tools`, SQLite) are at least moderately recent.

## Next Priorities  
1. **Finish Operations Centre:** Complete all observability tasks from the plan (tables, HTML, sheets, alerts) to gain visibility.  
2. **Audit & Clean-Up:** Have Opus audit the new monitoring code; fix any performance issues.  
3. **User Feedback:** Once monitoring is live, solicit feedback on alert quality and source performance to refine filters/ontology.  
4. **Add Tests:** Cover critical pipelines and telemetry with tests.  
5. **Onboarding:** Document runbook for using the system (e.g. how to interpret the dashboard).  

## Recent Major Changes  
- **2026-07-30:** Implemented dynamic polling logic (increased ingestion throughput by ~15%).  
- **2026-07-25:** Introduced partial observability (basic counts of passed filters printed in logs).  
- **2026-07-10:** Added new source (“German OAM”) and updated ontology tags.  
- **2026-06-20:** Reconfigured deduplication: now checking for duplicate *issuer* as well as article.  
- **2026-06-05:** Switched AI inference from synchronous to batch mode (faster throughput with async calls).  

(*Note: This file is auto-generated by the SSR Operations Centre on each release.*)  
```

# Next Steps (Checklist)

- **Gemini (Engineer):**  
  - [ ] Review this report and the above plan; integrate missing tables and logging hooks as specified.  
  - [ ] Run `python3 monitor.py` and confirm no logic changes to alert output.  
  - [ ] After changes, push code and trigger the workflow. Verify the GitHub Actions log shows the monitoring steps executing (DB writes, HTML generation, Sheets API calls).  
  - [ ] Validate the HTML dashboard at `docs/index.html` is formatted correctly and includes all new columns. Test filtering/sorting works client-side.  
  - [ ] Check Google Sheets “Daily Statistics” has exactly one new row (with yesterday’s totals) after midnight run, and “AI Usage” appends run data.  
  - [ ] Perform a failure test (e.g. kill monitor.py mid-run) and ensure `exceptions_log` captures it and sets health appropriately.  
  - [ ] Commit all changes, update dependencies list if any (e.g. `requirements.txt`), and merge to `main`.

- **Opus (Auditor):**  
  - [ ] Examine the new SQLite schema by querying `pipeline.db`; ensure tables exist with correct columns and indexes (e.g. primary keys on dates).  
  - [ ] Run benchmarks: instrument monitor.py with a timer to confirm <2% overhead (processing 20k articles).  
  - [ ] Code review: ensure no sensitive info (API keys) is logged. Confirm exceptions are handled gracefully.  
  - [ ] Check the HTML (docs/index.html) does not contain any hard-coded secrets or dynamic scripts.  
  - [ ] Review the `PROJECT_STATE.md` for accuracy against implementation.  
  - [ ] Ensure the Google Sheets “System Settings” tab was created with default values and can be edited without breaking the code.  

# Questions / Clarifications for the User  

- Are all desired Google Sheets for “Daily Statistics”, “AI Usage”, and “Source Statistics” already created and accessible to the service account (or should the code auto-create them)?  
- Do any legacy data needs migrating? For example, should the first runs after deployment backfill last 14 days of logs into `article_lifecycle_log`?  
- Is there any expected runtime SLA (e.g. alert if monitor.py > 4.5 minutes) beyond the drift detection?  
- Confirm the naming scheme and roles for AI keys (exactly 7 Google, 9 OpenRouter) so we use consistent masked IDs.  
- Any preferences for HTML design (colors, logos) for the dashboard, or is a simple table with minimal styling acceptable?  

```  
