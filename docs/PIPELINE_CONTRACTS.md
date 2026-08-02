# SSR Pipeline Stage Interface Contracts
*Document Version: 1.0.0 (Production Actual)*

This document defines the strict interface contracts for every computational stage within the Special Situations Radar (`monitor.py`). These contracts guarantee deterministic data flow and define exactly how state mutates between the network edge and the alerting layer.

---

## Stage 1: Ingestion & Deduplication

### **Purpose**
To systematically poll external financial wire feeds, extract raw filing data, and discard duplicate articles before they enter the computational pipeline.

* **Inputs:** Target feed configuration (Scraper Class, URLs, Polling Frequency).
* **Outputs:** A structured dictionary containing raw, unique filing data (`title`, `body`, `url`, `source`, `timestamp`).
* **Database Writes:** * `INSERT INTO articles` (Status: `PENDING`) for unique items.
    * `INSERT INTO article_lifecycle_log` (Outcome: `issuer_duplicate`) for items matching existing hash keys.
* **External Dependencies:** Target HTTP/RSS endpoints (e.g., PR Newswire, GlobeNewswire), local residential proxy network.
* **Failure Modes:** Connection timeouts, HTTP 403 Forbidden (WAF blocks), parsing failures due to DOM changes.
* **Retry Behaviour:** Exponential backoff on HTTP 429 (Rate Limit). No retry on 403.
* **Side Effects:** Emits standard output logs for ingestion counts.
* **Invariants:** * No item with a previously seen `article_key` (URL/ID hash) may proceed to Stage 2.
    * All timestamps must be localized to strict UTC.

---

## Stage 2: Ontology Parsing

### **Purpose**
To perform semantic filtering via compiled regular expressions, determining if the raw text matches the taxonomy of a targeted special situation.

* **Inputs:** `title` (String), `body` (String) from Stage 1 output.
* **Outputs:** A defined `event_family` classification (e.g., `SCHEME_OF_ARRANGEMENT`, `SHARE_BUYBACK`) or `None`.
* **Database Writes:** * If `None`: `INSERT INTO article_lifecycle_log` (Outcome: `ontology_rejected`).
* **External Dependencies:** In-memory cached regex rules retrieved from Google Sheets cache.
* **Failure Modes:** Malformed regex execution timeout, character encoding mismatches.
* **Retry Behaviour:** No retry. Synchronous memory execution.
* **Side Effects:** Memory allocation for multi-matrix regex evaluation.
* **Invariants:** * Case-insensitive matching is strictly enforced.
    * Output must map strictly to a pre-defined `event_family` enum; arbitrary classifications are fatal.

---

## Stage 3: Rules Engine Scoring

### **Purpose**
To evaluate the matched event against specific playbook thresholds (e.g., Market Cap minimums, historical liquidity) to eliminate sub-optimal financial opportunities.

* **Inputs:** `event_family` profile from Stage 2, extracted quantitative entity data (Market Cap, Volume).
* **Outputs:** A normalized numeric confidence score (0.0 to 100.0).
* **Database Writes:** * If Score < Playbook Minimum: `INSERT INTO article_lifecycle_log` (Outcome: `rules_rejected`).
* **External Dependencies:** None (Relies entirely on extracted entity data).
* **Failure Modes:** Missing entity quantitative data (returns default low score).
* **Retry Behaviour:** No retry. Synchronous memory execution.
* **Side Effects:** None.
* **Invariants:** * Output score must always be a float between 0.0 and 100.0.
    * A missing minimum threshold immediately fails the contract (returns 0.0).

---

## Stage 4: AI Contextual Evaluation

### **Purpose**
To utilize Large Language Models (LLMs) to perform complex contextual analysis on the filing text, determining if the event meets the qualitative bar for alpha generation.

* **Inputs:** System prompt configuration, raw filing text, associated quantitative metadata.
* **Outputs:** A structured JSON object defining actionable status and reasoning summary.
* **Database Writes:** * Updates `article_lifecycle_log` (Sets `ai_invoked=1`, records `processing_time_ms`).
* **External Dependencies:** OpenRouter API or Gemini API network endpoints.
* **Failure Modes:** API timeouts, context window overflow (Token limit exceeded), malformed JSON response.
* **Retry Behaviour:** Single retry on HTTP 500/503/504 errors. No retry on context window overflow.
* **Side Effects:** Triggers API billing usage.
* **Invariants:** * Must strictly return valid, parseable JSON matching the requested schema.
    * API keys must be injected securely via local environment variables.

---

## Stage 5: Alerting & Dispatch

### **Purpose**
To dispatch fully qualified special situations to targeted downstream communication layers (e.g., Email, Webhooks).

* **Inputs:** The validated JSON event payload from Stage 4.
* **Outputs:** Delivery status code (`True` or `False`).
* **Database Writes:** * Updates `article_lifecycle_log` (Final Outcome: `PASSED (Alerted)`).
    * Updates `articles` (Status: `DISPATCHED`).
* **External Dependencies:** Outbound SMTP relays or Webhook endpoints.
* **Failure Modes:** SMTP connection refusal, Webhook timeout.
* **Retry Behaviour:** Exponential backoff for up to 3 attempts.
* **Side Effects:** Triggers external notifications.
* **Invariants:** * Must not block the primary execution loop on failure (Asynchronous dispatch).
    * Event data must not be altered during transit formatting.
