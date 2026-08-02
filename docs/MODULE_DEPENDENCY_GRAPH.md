# SSR Module Dependency & Import Graph
*Document Version: 1.0.0 (Repository Static Analysis)*

This document maps all incoming and outgoing module dependencies across the Special Situations Radar codebase, identifying architectural coupling, potential cycles, and isolated utility scripts.

---

## 🗺️ Mermaid Module Dependency Graph

```mermaid
graph TD
    %% Entrypoints & Orchestrators
    Monitor[monitor.py] --> SQLite[(ssr_cache.sqlite)]
    Monitor --> SheetsClient[Google Sheets API]
    Monitor --> AIClient[OpenRouter / Gemini API]

    %% Validation Suite Modules
    CovReport[src.validation.coverage_report] --> ValDB[(validation.db)]
    Benchmark[src.validation.benchmark] --> ValDB
    MissedOps[src.validation.missed_ops] --> ValDB
    CoverageAudit[src.validation.coverage_audit] --> ValDB
    Tracer[src.validation.tracer] --> ValDB

    %% Inter-module relationships
    Monitor -.->|Decoupled execution via CLI| CovReport
    Monitor -.->|Decoupled execution via CLI| Benchmark
    Monitor -.->|Decoupled execution via CLI| MissedOps
