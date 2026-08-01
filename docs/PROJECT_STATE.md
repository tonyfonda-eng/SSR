# Special Situations Radar - Project State

## Current Version
**v1.1 (Stabilised)**

## Architecture Summary
Special Situations Radar (SSR) is a Python-based, AI-assisted event-driven research platform. It continuously scrapes news wire feeds (HTML & RSS), applies a rule-based Multi-Channel Evidence Scoring system defined in Google Sheets, and leverages LLMs (Google Gemini / OpenRouter) for intelligent event classification, ticker extraction, and investment memo generation. Core philosophy: "Python executes, Google Sheets decides."

## Completed Systems
*   **Ingestion Pipeline:** Custom HTML scrapers (PR Newswire, BusinessWire, GlobeNewswire, SEC EDGAR, KEDM, LSE) with RSS fallbacks.
*   **Language-Agnostic Ontology Layer (`src/ontology`):** Replaces rigid regex with abstract Semantic Concepts (e.g., `ACQUISITION`) and Event Statuses (e.g., `COMPLETED`) for multi-lingual coverage.
*   **Multi-Channel Rules Engine:** Dynamically calculates article scores based on Ontology, Keywords, Event Status, Document Type, and Source Reliability.
*   **AI Circuit Breakers:** Robust 429/404 exhaustion handling that safely aborts pipeline loops to prevent infinite hangs and quota waste.
*   **Deduplication & Cache:** Two-tier system utilizing a persistent SQLite cache (`ssr_cache.sqlite`) for URL tracking and a "Daily Memory" (Google Sheets) for syndicated issuer deduplication.
*   **Automated CI/CD:** GitHub Actions workflow executing every 5 minutes with strict concurrency limits.
*   **Operations Centre Dashboard:** Automatically generated static HTML dashboard (`docs/index.html`) published to GitHub Pages tracking health, AI capacity, and pathologically slow articles.

## Systems Under Development
*   **T12 Structural Floor Analytics:** Enhancing the "Resumption of Trading" event playbook to calculate net cash per share metrics on halted stocks.
*   **M&A Naked Call Strategy:** Integrating options chain availability directly into the ingestion loop to identify actionable M&A spreads.

## Known Issues
*   **Backlog Processing Time:** Following a significant pipeline outage (e.g., exhausted API keys), the initial recovery run can take 30+ minutes to clear the accumulated unanalyzed articles in the queue.

## Technical Debt
*   **`monitor.py` Size:** The main runner has grown significantly (~970 lines) and could benefit from further modularization (specifically moving the dashboard, metrics aggregation, and daily memory classes into dedicated service files).

## Next Priorities
*   Refine the **Naked Call Strategy** playbook using the "MKTX/ICE" Gold Standard case study to automatically calculate annualized ROI.
*   Expand the **Semantic Concepts** and **Event Statuses** in Google Sheets to increase coverage accuracy for European/Asian markets.
*   Monitor the new `Ontology Review` tab in Google Sheets to refine translation rules based on missed non-US articles.

## Recent Major Changes
1.  **Dashboard Deployment:** Added `permissions: contents: write` to the GitHub Actions workflow to successfully automate the deployment of the operations dashboard to GitHub Pages.
2.  **Daily Memory Fix:** Corrected a bug in `src/sheets.py` that prevented the pruning of the Daily Memory tab when there were fewer than 100 rows to delete.
3.  **Ontology Migration:** Completed the transition from legacy, language-specific translation rules to the new language-agnostic Semantic Ontology scoring model.
