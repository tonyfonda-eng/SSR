# SSR Complete Data Lineage & Lifecycle Analysis
*Document Version: 1.0.0 (Production Data Governance)*

This document traces every data entity and field processed by the Special Situations Radar (`monitor.py` and Validation suite), detailing its exact origin, intermediate transformations, persistent storage destination, downstream consumers, and deletion policies.

---

## 📊 Core Data Entities Lineage Matrix

| Data Entity / Field | Origin | Transformations | Storage | Consumers | Deletion Policy |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Raw Filing Payload**<br>`title`, `body`, `url`, `source`, `timestamp` | External wire feeds (PR Newswire, GlobeNewswire via HTTP/RSS scrapers) | Sanitized into UTF-8 strings; URL hashed into unique `article_key`. | SQLite Cache (`ssr_cache.sqlite` -> `articles` table) | Deduplication engine, Ontology filter, AI evaluation gateway | Retained for historical analytics; purged periodically based on local storage retention thresholds. |
| **2. Issuer Metadata Cache**<br>`ticker`, `company_name`, `watchlist_flags` | Google Sheets API V4 (Dynamic Daily Memory) | In-memory parsing into active lookup dictionaries (`dict`). | In-memory RAM during session runtime. | Filtering loop, entity matching checks. | Flushed on process termination; refreshed on every orchestrator startup. |
| **3. Ontology & Rules Lexicons**<br>`concept_patterns`, `status_patterns`, thresholds | Google Sheets / Local configuration definitions | Compiled into optimized, case-insensitive regex objects via Python `re` module. | In-memory RAM cache. | Ontology parser (`evaluate_ontology()`), Rules engine (`evaluate_playbook_rules()`). | Flushed on process termination. |
| **4. Article Lifecycle Logs**<br>`article_key`, `pipeline_stage`, `outcome`, `ai_invoked`, `processing_time_ms` | Generated internally during pipeline execution steps. | Formatted into structured operational metrics and timestamps. | SQLite Cache (`ssr_cache.sqlite` -> `article_lifecycle_log` table) | VQA auditors, coverage reporters, debugging monitors. | Retained indefinitely for QA auditing and metric trend analysis. |
| **5. Validation KPI Metrics**<br>`capture_rate`, `coverage`, `false_positives`, `false_negatives`, `avg_delay` | Computed via QA scripts (`coverage_report.py`, `benchmark.py`) | Aggregated into percentage drifts and delta summaries. | Validation Database (`validation.db` -> `coverage_weekly_metrics`) | `docs/COVERAGE_REPORT.md`, Validation Master Plan dashboard. | Appended weekly; historical snapshots preserved for drift tracking. |

---

## 🔄 Detailed Field-by-Field Lifecycle Breakdown

### Entity 1: Raw Filing Payload (`title`, `body`, `url`, `source`, `timestamp`)
* **Origin:** Downloaded via HTTP GET requests from external financial wire aggregators.
* **Transformations:** Converted from raw HTML/XML feeds into structured Python dictionaries. A cryptographic hash of the URL is generated to establish the `article_key`.
* **Storage:** Written to `ssr_cache.sqlite` under the `articles` table with a `PENDING` initial status state.
* **Consumers:** Consumed sequentially by the Deduplication Engine, Ontology Filter, and AI Evaluation Gateway.
* **Deletion:** Retained in local SQLite storage for duplicate prevention; old records can be archived or pruned via background database maintenance tasks.

### Entity 2: Article Lifecycle Logs (`outcome`, `pipeline_stage`, `ai_invoked`)
* **Origin:** Generated at each conditional gate inside `monitor.py` (e.g., `issuer_duplicate`, `ontology_rejected`, `rules_rejected`, `PASSED (Alerted)`).
* **Transformations:** Logged alongside execution timestamps and processing durations in milliseconds.
* **Storage:** Persisted in `ssr_cache.sqlite` (`article_lifecycle_log`) and mirrored in `validation.db` during QA audits.
* **Consumers:** Audited by VQA scripts (`coverage_report.py`, `missed_ops.py`) to calculate pipeline capture and error rates.
* **Deletion:** Maintained permanently as part of the immutable validation and compliance audit trail.

---

## 🔒 Data Governance Invariants
1. **Zero Production Mutation:** Validation and VQA tools (`src/validation/`) are strictly restricted from mutating production article payloads or cache states.
2. **Deterministic Hashing:** The `article_key` field must be derived deterministically from the filing URL to prevent duplicate ingestion across separate polling intervals.
