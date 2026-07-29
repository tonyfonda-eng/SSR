# The SSR Constitution: Living Architecture

This document defines the intent, vision, and operating principles of the Special Situations Radar (SSR). It is the source of truth for what SSR is trying to become.

## 1. Vision
To operate as an autonomous, highly-selective, 24/7 intelligence radar that actively monitors global data feeds to identify actionable, publicly-traded special situations (corporate cash events) in near real-time, while operating entirely on a $0/month serverless infrastructure.

## 2. Principles
- **Signal over Noise:** 99% of financial news is irrelevant marketing or noise. The system's primary job is not just to find signals, but to ruthlessly destroy noise before it reaches a human.
- **Asymmetric Returns:** SSR hunts for specific, hard-catalyst situations (Cash Mergers, Spin-offs, Liquidations, Take-Privates) where the payoff is highly asymmetric.
- **Zero-Friction Configuration:** The Python codebase should remain static. All dynamic logic, keyword tuning, exclusions, and AI training must be controlled by non-technical humans via Google Sheets. 
- **Robust Redundancy:** The architecture must be self-healing. If HTML scrapers are blocked, it falls back to RSS. If an AI key hits a rate limit, it instantly rotates to a backup key.

## 3. The Pipeline
SSR operates as a multi-stage gauntlet. If an article survives the gauntlet, it triggers an alert.

1. **Ingestion (The Wide Net):** GitHub Actions awake every 5 minutes to scrape hundreds of articles from PR Newswire, GlobeNewswire, and SEC EDGAR.
2. **Pre-Filtering (The Shields):**
   - *Global Exclusions:* Instantly drops articles containing known spam phrases or PR firms.
   - *Regex Ticker Filter:* Scans for global exchange formats (e.g., `NASDAQ: AAPL`, `LSE: VOD`). If 0 tickers are found, it assumes the article is about a private company and instantly drops it.
3. **The Rules Engine (The Dumb Filter):** Evaluates articles against the Google Sheet keywords. If an article accumulates enough points (threshold), it proceeds.
4. **AI Interrogation (The Smart Filter):**
   - *Classification & False Positives:* Gemini AI reads the article to determine intent. It can reject borderline marketing stunts as "False Positives".
   - *Target Extraction:* The AI identifies the primary *subject* of the event. If the target is a private company being bought by a public company, the AI rejects it.
   - *Playbook Execution:* The AI acts as a junior analyst, reading the article to answer specific research questions (premium, expected close date, etc.).
5. **Alerting:** The bot packages the rules engine evidence and the AI research summary into a high-priority email.

## 4. Workbook Structure (The Control Center)
The Google Sheet is the brain of SSR. It consists of:
- **Rules:** The core logic matrix. Maps keywords, point modifiers, rule-specific exclusions, and custom AI training prompts to specific Event Families.
- **Global Exclusions:** The universal blacklist. A simple list of words/phrases that guarantee instant rejection.
- **Sources:** Tracks the URLs being scraped and logs the ingestion performance of the bot.
- **Playbooks:** Defines the exact research questions the AI must answer for each specific Event Family (e.g., different questions for a Merger vs a Spin-off).
- **AI Research Queue:** A historical log of processed events for human auditing.

## 5. Human vs Bot Responsibilities
**The Bot is responsible for:**
- Ceaseless 24/7 ingestion of thousands of articles.
- Ruthless filtering of private equity noise and marketing spam.
- Formatting structured evidence and answering preliminary research questions.
- Never sleeping and never missing a catalyst.

**The Human is responsible for:**
- Tuning the "Brain": Updating the Google Sheet to refine keywords, add global exclusions when new spam patterns emerge, and writing smarter AI prompts.
- Executing the Trade: Evaluating the final, highly-curated email alerts and risking capital.

## 6. What SSR does NOT do
- **It does NOT execute trades.** It is an intelligence radar, not a trading algorithm.
- **It does NOT care about private companies.** A public company buying a private startup is irrelevant noise. The target *must* be tradable on global markets.
- **It does NOT perform fundamental analysis.** It will not read balance sheets, build DCF models, or analyze SEC 10-Ks. It hunts for *events*, not *value*.
- **It does NOT rely on paid APIs.** It leverages free tiers (GitHub Actions, Google Sheets, Google Gemini API Rotation) to achieve enterprise-grade scale at zero cost.

---

## 7. The Institutional Roadmap

The goal is to evolve SSR into something larger than an alert bot. It conceptually has four distinct layers:
1. **Sources** (Ingestion)
2. **Intelligence Engine** (Filtering & Extraction)
3. **Research Engine** (AI Playbooks)
4. **Knowledge Base** (Institutional Memory)

The Knowledge Base is what will make SSR genuinely unique. Every event, every decision, every outcome, and every lesson becomes part of a growing institutional memory. After a year, SSR won't just tell you *what happened today*—it will be able to say *how similar situations played out historically* and whether this one deserves your attention.

**The 15 Missing Systems to Build:**
1. **Explainability Engine (Completed):** Every alert must generate a structured "Trigger Summary" explaining exactly why it passed (Matched keywords, AI Confidence, Classification).
2. **Confidence Scoring:** Move beyond binary events. Score Rules confidence, AI confidence, Extraction confidence, and Overall confidence.
3. **Event Lifecycle Tracking:** One announcement is not one event. Follow the lifecycle from "Offer Announced" -> "Competing Bidder" -> "Regulator Approval" -> "Archived".
4. **Company Memory:** SSR should know the history. If Boeing has a new alert, SSR should already know its past spin-offs, activist campaigns, and historical alerts.
5. **Relationship Graph:** Connect entities (e.g., Apollo -> owns -> Company A -> bid for -> Company B).
6. **Event Deduplication:** If PR Newswire, Reuters, and SEC all report the same transaction, it should be logged as ONE case, not three separate alerts.
7. **Case Workspace:** Turn ephemeral emails into persistent workspaces with timelines, documents, SEC filings, and AI notes.
8. **Continuous AI Research:** Update research, confidence, and emails automatically as new documents hit the wire for an existing event.
9. **Research Gap Detection:** AI should explicitly list what it *doesn't* know (e.g., Break fee, Expected close, Financing source).
10. **Analyst Question Generator:** AI produces a list of questions the human portfolio manager should investigate.
11. **Opportunity Ranking:** Score alerts 0-100 based on Premium, Spread, Liquidity, Probability, and Complexity so humans know what to read first.
12. **False Positive Learning:** When a human clicks "False positive", SSR learns from the mistake without requiring code changes.
13. **Research Notebook:** Store every AI run forever to compare the "First opinion" against the "Final outcome" to improve prompts over time.
14. **Outcome Database:** Log every completed deal (Closed, Failed, Higher bid, Final IRR) so SSR becomes its own training dataset.
15. **Strategy Analytics:** Track win rates, average premiums, average spreads, and holding periods grouped by sector, country, or AI prompt version to continuously improve strategy.

---

## 8. Technical Architecture (For Future AI Agents)

This section is written specifically for future AI coding agents that are maintaining or upgrading the SSR codebase. 

### Core Stack & Environment
- **Language:** Python 3.11
- **Deployment:** GitHub Actions (serverless cron jobs triggering `monitor.py`).
- **Dependencies:** `beautifulsoup4`, `feedparser`, `requests`, `gspread`, `google-auth`, `google-genai`.
- **Secrets:** `GEMINI_API_KEY` (comma-separated list for rotation), `GOOGLE_SERVICE_ACCOUNT_JSON` (for gspread auth), `SMTP_*` variables for email.

### System Modules
- **`monitor.py`:** The primary orchestrator. Loops over sources, handles pre-filtering (Regex & Global Exclusions), triggers the Rules Engine, interrogates the AI, and manages database state.
- **`src/sheets.py`:** The control plane interface. Uses `gspread` to read Rules, Playbooks, Exclusions, and Sources from the Google Sheet. Also writes back to the "AI Research Queue".
- **`src/rules_engine.py`:** The dumb filter. Scores article text against keywords and confidence modifiers. Natively generates the `evidence_log` and `confidence` score.
- **`src/ai.py`:** The reasoning engine. Implements a client pool for Gemini API key rotation to bypass free-tier rate limits. Exposes three strict functions: `classify_event` (intent), `extract_target_ticker` (target isolation), and `execute_playbook` (12-section structured Investment Memo).
- **`src/database.py`:** The Knowledge Base (SQLite). Maintains relational state across runs. 
  - `articles`: Raw ingestion cache to prevent rescraping.
  - `events`: Deduplication state. Uses primary key `EventFamily_Ticker_YYYY_MM`.
  - `companies`: Tracks historical alert counts per ticker.
  - `research_logs`: Permanently logs AI memos and Rules scores for strategy analytics.
- **`src/alerts/email.py`:** The alerting interface. Deterministically stitches the Python-generated Evidence Log (Section 3) into the middle of the AI-generated Markdown memo to prevent hallucination of keyword matches.

### Critical Execution Flows
1. **Ticker Extraction & Deduplication:** AI extracts the target ticker. If it returns `"PRIVATE"`, `monitor.py` drops the article. If public, it calls `create_event_if_new(event_family, ticker)`. If this returns `None`, the event is a duplicate (e.g. syndicated news) and the article is dropped.
2. **Regex Pre-Filtering:** PR Newswire/GlobeNewswire bodies are scanned using a massive compiled regex list of global stock exchange acronyms. If `len(matches) == 0`, the article is instantly dropped before reaching the rules engine. (This check is bypassed for SEC EDGAR).
