# The SSR Constitution

SSR exists to discover, evaluate, and track investable public-company corporate events from first public disclosure through final resolution. 

It is not an alert bot; it is a **Case Management System**.

## 1. What SSR Optimizes For
Success is defined by the following metrics:
- Earliest possible detection.
- Lowest false-positive rate.
- Highest information density.
- Complete event history.
- Reproducible decisions.

## 2. Core Principles
- **Truth over Speed:** SSR will sacrifice speed where necessary to improve confidence and reduce false positives. You are not trying to beat Reuters by 3 seconds; you are trying to be right.
- **Determinism before AI:** The pipeline must always prefer deterministic logic over probabilistic reasoning. Use Regex before LLMs; use structured extraction before free-text interpretation; use exact rules before semantic inference. This reduces cost, latency, and hallucinations.
- **Explainability:** Every recommendation produced by SSR must be traceable, reproducible, and auditable. No alert should exist without a clear chain of evidence explaining why it survived each stage of the pipeline.
- **Time is the Metric:** Every single alert must save the human analyst time.

## 3. The Conceptual Pipeline
Articles are ephemeral. They disappear after ingestion. The **Case** is the permanent object, and everything hangs off that.

1. **Sources** (Ingestion of ephemeral articles)
2. **Evidence Collection** (Gathering raw text and rules matches)
3. **Evidence Filtering** (Regex, Exclusions)
4. **Case Creation** (Event deduplication and instantiation)
5. **Case Enrichment** (Target extraction, relationship mapping)
6. **Case Scoring** (Multi-layered confidence generation)
7. **Case Research** (AI Playbook execution and questioning)
8. **Human Decision** (Capital allocation)
9. **Outcome Tracking** (Success/Failure logging)
10. **Knowledge Base** (Permanent institutional memory)

## 4. Tracked Event Families
SSR only tracks specific, hard-catalyst situations with asymmetric payoffs. Everything else is noise unless explicitly enabled.
- Cash mergers
- Take-privates
- Tender offers
- Schemes of arrangement
- Liquidations
- Spin-offs
- Asset sales
- Reverse takeovers
- Major restructurings
- Rights affecting value
- Court-approved reorganizations

## 5. Human vs Bot Responsibilities

### The Bot
- Observes feeds relentlessly.
- Filters out noise deterministically.
- Researches facts objectively.
- Documents findings meticulously.
- Ranks opportunities mathematically.
- Learns from outcomes continuously.
- **Never decides.**

### The Human
- Judges the research.
- Prioritizes the pipeline.
- Allocates capital.
- Overrides the AI when necessary.
- Improves the system logic.
- **Owns the risk.**
