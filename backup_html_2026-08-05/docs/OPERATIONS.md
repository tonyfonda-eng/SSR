# System Operations

This document covers everything related to system health, monitoring, and maintenance.

## The Operations Centre Dashboard
The system automatically generates a static HTML dashboard at `docs/index.html`. This dashboard is deployed to GitHub Pages via the CI workflow.

### Key Metrics
*   **Health Score (0-100):** A composite score derived from pipeline runtime, unhandled exceptions, and API exhaustion. If the pipeline hangs for >4 minutes or throws a fatal error, the score plummets to Critical.
*   **Avoided AI %:** The percentage of downloaded articles that were successfully destroyed by Global Exclusions, Ontology filtering, or the Rules Engine *before* ever hitting the expensive AI APIs.
*   **Pipeline Funnel:** A step-by-step count of exactly where articles are being dropped.
*   **AI Capacity Forecast:** Tracks API calls across all keys to estimate daily quota remaining for Google Gemini and OpenRouter.
*   **Pathological Cases:** Logs the Top 10 slowest articles processed, highlighting which specific stage caused the bottleneck.

## SQLite Cache & Housekeeping
The `ssr_cache.sqlite` database is the true source of state for the system.
*   **Persistence:** It tracks the unique IDs of all downloaded articles to prevent infinite reprocessing loops.
*   **Housekeeping:** At the end of every pipeline run, the `perform_housekeeping()` function runs. It automatically prunes raw article bodies older than 14 days to keep the database lightweight (preventing GitHub Actions cache bloat).

## Daily Statistics Sync
At the end of every run, the system checks if yesterday's operational metrics have been synced to Google Sheets.
*   If not, it aggregates all pipeline funnels, source reliability metrics, and AI response times, and pushes them to the `Daily Statistics`, `Source Statistics`, and `AI Usage` tabs.
*   This ensures long-term historical tracking of pipeline degradation without relying on ephemeral logs.

## Drift Alerts
The system actively monitors a rolling 30-day average of ingestion metrics.
*   If total downloads drop by >20% compared to the 30-day average, or if the AI Success rate drops below 80%, a **Critical Drift Alert** email is automatically sent to the administrator to investigate potential scraper blocks or API outages.
