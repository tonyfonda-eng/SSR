# SSR Orchestration Refactor Plan
*Phase: Architectural Decoupling*

**Objective:** Strip all business logic, data transformations, and state mutations out of `monitor.py`. The orchestrator must be reduced to a pure control-flow loop coordinating isolated, single-responsibility modules.

---

## 🛑 Violation 1: Database Initialization & Query Execution
**Current Location:** `monitor.py` -> `main()` and inline SQLite `cursor.execute()` calls throughout the scraping loop.
* **Description:** The orchestrator manually creates SQLite schemas (`CREATE TABLE IF NOT EXISTS`) and writes deduplication logic directly to the disk.
* **Recommended Destination:** `src/database/cache_manager.py`
* **Estimated Complexity:** Low
* **Risk of Change:** Low. (Pure structural move; no logic changes required, just abstracting the SQL queries into callable methods like `save_article()` or `is_duplicate()`).

## 🛑 Violation 2: State Recovery & Google Sheets API Integration
**Current Location:** `monitor.py` -> `load_issuer_cache()` & `load_ontology_rules()`
* **Description:** The orchestrator handles Google V4 API authentication, network requests, and JSON parsing to build the daily memory caches.
* **Recommended Destination:** `src/ingestion/sheets_client.py`
* **Estimated Complexity:** Medium
* **Risk of Change:** Low. (Moving network logic out of the main thread makes the orchestrator significantly cleaner and allows for isolated API mock testing).

## 🛑 Violation 3: The Deduplication Gatekeeper Logic
**Current Location:** `monitor.py` -> Scraping Loop
* **Description:** The orchestrator manually hashes the URL/ID, checks the SQLite cache, and dictates whether the loop continues or aborts.
* **Recommended Destination:** `src/pipeline/deduplicator.py`
* **Estimated Complexity:** Low
* **Risk of Change:** Medium. (If the abstraction is handled incorrectly, the pipeline could ingest duplicates, inflating AI costs and false positive alerting).

## 🛑 Violation 4: Rules & Ontology Matrix Evaluation
**Current Location:** `monitor.py` -> `evaluate_ontology()` and `evaluate_playbook_rules()`
* **Description:** The orchestrator is compiling regex strings and calculating float scores to determine playbook validity.
* **Recommended Destination:** `src/engine/ontology.py` and `src/engine/rules.py`
* **Estimated Complexity:** High
* **Risk of Change:** High. (This is the core alpha-generation logic. Decoupling this requires precise interface contracts to ensure the dictionaries passed from the orchestrator match what the engines expect).

## 🛑 Violation 5: AI Payload Construction & Network Dispatch
**Current Location:** `monitor.py` -> `invoke_llm_analysis()` and `dispatch_alert()`
* **Description:** The orchestrator builds the system prompts, formats the JSON string for the LLM, and manages the outbound SMTP/Webhook connections.
* **Recommended Destination:** `src/ai/evaluator.py` and `src/dispatch/alerter.py`
* **Estimated Complexity:** Medium
* **Risk of Change:** Medium. (Requires careful handling of environment variables for API keys outside of the main scope).

---

## 🏁 Execution Strategy & Recommendation
**Do not execute this refactor yet.** As stated in the `VALIDATION_MASTER_PLAN.md`, the system is currently under a strict feature and code freeze until the **Opportunity Capture Rate** metrics stabilize. 

Once the pipeline achieves a 0% False Negative rate based on the current architecture, execute this refactor incrementally (Violation 1 first, verify with tests, then Violation 2). Do not attempt a total rewrite in a single pull request.
