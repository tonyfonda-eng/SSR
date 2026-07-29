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
