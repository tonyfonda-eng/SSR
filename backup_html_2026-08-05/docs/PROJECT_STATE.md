# SSR Project State

**Version:** 3.2.0 (Architecture Review Baseline)
**Last Updated:** August 2026

## Executive Overview
SSR (Special Situations Radar) is an event-driven discovery pipeline engineered to isolate rare corporate actions and structural mispricings ahead of broad market awareness. The system operates autonomously, processing high-throughput unstructured news text deterministically before utilizing sandboxed LLMs for high-conviction thematic research. 

## Design Principles
- **Event-Centricity:** Articles are temporary; events are permanent. The system tracks the lifecycle of corporate situations, not merely the news cycle.
- **Deterministic Filtering First:** Official regulatory parsers, strict regex filters, and hardcoded ontology keyword matching always precede AI invocation to protect API quotas and execution speed.
- **Component Isolation:** - **Python** executes logic and orchestration.
  - **Google Workbooks** contain the firm's intellectual property (rules, ontology, playbooks).
  - **SQLite** stores operational memory and telemetry.
  - **Operations Centre** measures system quality.
  - **Humans** allocate capital.

## Current Priorities
New feature development is currently paused. The overriding engineering mandates are:
- **Robustness & Reliability:** Ensure the pipeline can run unattended for months without fatal failures.
- **Observability:** Maintain strict, deterministic tracking of pipeline drop-offs and API latency.
- **Quality Over Coverage:** Prioritize high-signal alerts (e.g., odd-lot tenders, naked calls) over processing every possible newswire feed.

## Long-Term Direction
The architectural evolution of SSR follows a strict maturation path:
`Articles` → `Events` → `Research` → `Knowledge` → `Investment Decision`

## Implementation Status Matrix

| Component | Status | Description |
| :--- | :--- | :--- |
| **Ingestion Engine** | Partially Implemented | RSS and custom HTML scrapers pull articles; dynamic polling adjustments are active. |
| **Deterministic Funnel** | Implemented | Single-pass evaluation applying global exclusions, regex, and exact-match ontology filters. |
| **Research Layer** | Implemented | Sandboxed AI classification and playbook execution generating investment memos. |
| **Operations Centre** | Implemented | Static HTML dashboard and Google Sheets sync tracking 30-day drift and pipeline health. |
| **Event-ID Tracking** | Planned | Transitioning from article-level tracking to persistent corporate event clusters. |
| **Knowledge Database** | Deferred | Long-term storage of resolved events for historical backtesting. |
| **Automated Execution** | Deferred | Direct integration with brokerage APIs (e.g., IBKR) for immediate capital deployment. |

## Known Technical Debt
- **Ingestion Loop Overlap:** Custom scrapers and RSS feeds are processed sequentially inside the main loop, risking timeout bottlenecks during heavy news days.
- **Pseudo-Event Generation:** Current event IDs rely heavily on basic ticker concatenation (`TICKER_YYYY_MM_DD`) rather than deep semantic clustering across multiple sources.