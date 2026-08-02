# SSR Architecture Verification & Drift Analysis
*Document Version: 1.0.0 (System Governance Audit)*

This document compares the intended modular architecture of the Special Situations Radar against its actual runtime implementation (`monitor.py`), identifying structural drift, layer violations, hidden coupling, and improper responsibility allocations.

---

## 🔍 Intended vs. Actual Architecture Comparison

| Architectural Dimension | Intended Design | Actual Implementation | Drift Severity |
| :--- | :--- | :--- | :--- |
| **Control Flow** | Pure event-driven orchestrator invoking decoupled modules. | Procedural "God Object" script (`monitor.py`) executing inline business logic. | 🔴 **High** |
| **Data Access** | Isolated repository and service layers abstracting persistence. | Direct, inline SQLite cursor executions (`cursor.execute()`) scattered across loops. | 🟡 **Medium** |
| **Configuration State** | Immutable configuration objects injected at runtime. | Dynamic, synchronous API pulls from Google Sheets V4 embedded in runtime routines. | 🟡 **Medium** |
| **Validation Bounds** | Independent QA pipeline operating on read-only snapshots. | Isolated validation schema (`validation.db`) successfully decoupled from production. | ✅ **Aligned** |

---

## 🛑 Architectural Findings & Violations

### 1. Layer Violations
* **Observation:** The root orchestrator (`monitor.py`) directly invokes SQLite database operations, HTTP wire polling, regular expression evaluations, and external API requests within the same execution stack.
* **Impact:** Blurs the line between presentation/orchestration logic and persistence/domain layers, making isolated unit testing impossible without live network and database mocking.

### 2. Hidden Coupling
* **Observation:** Runtime evaluation is tightly coupled to external Google Sheets spreadsheets for issuer watchlists and ontology pattern rules (`load_issuer_cache()` and `load_ontology_rules()`).
* **Impact:** If the Google Sheets API experiences latency or authentication timeouts during a polling cycle, the entire financial monitoring thread stalls or fails.

### 3. Missing Abstractions
* **Observation:** Filings and articles are passed between pipeline stages as raw, untyped Python dictionaries (`dict`), leading to fragile key-lookup access patterns across modules.
* **Impact:** Increases vulnerability to `KeyError` exceptions if upstream scrapers alter raw metadata keys.

### 4. State Duplication
* **Observation:** Article lifecycle states are split redundantly across the `articles` persistence table (tracking primary ingest status) and the `article_lifecycle_log` audit table.
* **Impact:** Risk of state drift between primary record status and audit log outcomes if a transaction commit fails mid-stream.

### 5. Improper Responsibility Allocation
* **Observation:** `monitor.py` acts as the traffic controller, data transformer, regex matcher, rules scorer, AI client wrapper, and alerting dispatcher simultaneously.
* **Impact:** Violates the Single Responsibility Principle (SRP), resulting in high cyclomatic complexity ($\text{CC} = 14$) as noted in the complexity report.

---

## 🚀 Refactoring Roadmap Ranked by ROI

### **Priority 1: Extract Persistence & Ingestion Repositories**
* **Target:** Abstract SQLite queries into `src/database/repository.py` and wire scraping loops into `src/ingestion/scrapers.py`.
* **ROI:** **Highest.** Eliminates database clutter from the orchestrator and enables clean, mocked unit testing of core filters.
* **Estimated Effort:** Medium.

### **Priority 2: Introduce Typed Domain Models**
* **Target:** Replace raw dictionaries with typed dataclasses (e.g., `ArticlePayload`, `EventMatch`) for inter-stage communication.
* **ROI:** **High.** Prevents runtime key errors and enforces strict interface contracts between pipeline stages.
* **Estimated Effort:** Low.

### **Priority 3: Decouple Google Sheets Dependency**
* **Target:** Cache issuer lists and ontology lexicons locally at startup with background async refresh, rather than synchronous blocking calls during live loops.
* **ROI:** **Medium.** Eliminates single-point-of-failure network latency during time-sensitive filings.
* **Estimated Effort:** Medium.
