# SSR Static Code Complexity Report
*Document Version: 1.0.0 (Codebase Quality Audit)*

This document details the static complexity metrics for all active modules within the Special Situations Radar (`monitor.py` and the VQA suite), tracking lines of code, cyclomatic complexity, function lengths, branching factor, and nested depth against quality thresholds.

---

## 📊 Module Complexity Matrix

| Module | Lines of Code (LoC) | Max Cyclomatic Complexity (CC) | Avg Function Length | Max Branch Count | Max Nested Depth | Quality Flags Triggered |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`monitor.py`** | ~350 | 14 | 45 lines | 12 | 4 | 🚩 **CC > 10** (Orchestration Loop) |
| **`src/validation/coverage_report.py`** | ~140 | 6 | 35 lines | 5 | 3 | ✅ **Clean** |
| **`src/validation/verify_invariants.py`** | ~25 | 2 | 12 lines | 2 | 1 | ✅ **Clean** |

---

## 🚩 Flagged Complexity Violations

### 1. `monitor.py` — Core Execution Loop
* **Metric Violated:** Cyclomatic Complexity ($\text{CC} = 14$, Threshold $\le 10$).
* **Root Cause:** The orchestrator combines ingestion polling, deduplication conditional branching, regular expression ontology filters, rules engine checks, and AI response handlers inside a single procedural control flow.
* **Remediation Plan:** As outlined in `docs/ORCHESTRATION_REFACTOR.md`, this complexity will be resolved post-freeze by decoupling business logic into dedicated modules (`src/engine/` and `src/ingestion/`), reducing the orchestrator's branch count below the safety threshold.

---

## ⚙️ Automated Complexity Linting Hook

To measure local module complexity during development pre-flights, execute the standard Python radon/mccabe linter suite:

```bash
# Run complexity audit across python source trees
python3 -m radon cc monitor.py src/ -s
