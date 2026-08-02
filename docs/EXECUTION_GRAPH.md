# SSR Production Execution Graph & System Lineage
*Document Version: 1.0.0 (Production Actual)*

This document details the exact, deterministic runtime execution paths of the Special Situations Radar (`monitor.py`). It represents the literal implementation running on the production environment, tracking data state transformations from the network edge to localized databases and downstream channels.

---

## 🗺️ High-Level System Architecture

```mermaid
graph TD
    A[monitor.py Initialization] --> B[Database Check & Schema Verification]
    B --> C[Daily Memory: Fetch Issuer Cache]
    C --> D[Ontology Engine: Fetch Concept / Status Patterns]
    D --> E[Ingestion Matrix: Sequential Scraper Polling]
    E -->|PR Newswire / GlobeNewswire| F[Deduplication Phase: Check article_key]
    F -->|Unique Filing| G[Ontology Matrix: Filter Title / Body]
    G -->|Concept Matched| H[Rules Engine Matrix: Playbook Scoring]
    H -->|Threshold Passed| I[AI Evaluation: LLM Analysis]
    I -->|Actionable Event| J[Alerting & Dispatch Layer]
    J --> K[Database Lifecycle Logging & State Commit]
