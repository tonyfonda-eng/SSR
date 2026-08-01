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
