# The Ingestion Pipeline

The Special Situations Radar system processes every article through a strict, multi-stage funnel designed to eliminate noise as early as possible.

## 1. Data Ingestion (RSS & Scrapers)
The system wakes up every 5 minutes and iterates through the `Sources` tab. 
- It attempts to fetch articles using custom HTML scrapers (e.g., `src/scrapers/businesswire.py`).
- If a custom scraper fails or blocks the request (HTTP 403), it instantly falls back to parsing the RSS feed.

## 2. SQLite Deduplication (The Gatekeeper)
Every article URL/ID is checked against the local `ssr_cache.sqlite` database. 
- **If it exists:** It is immediately dropped. The system never processes the same article twice.

## 3. Global Exclusions (The Kill Switch)
The article text is checked against the `Global Exclusions` tab.
- If the text contains any blocked phrase (e.g., "quarterly earnings", "ex-dividend"), it is permanently archived and dropped.

## 4. Ontology Extraction
The text is scanned by the language-agnostic `src/ontology` module.
- It detects abstract `Semantic Concepts` (e.g., `ACQUISITION`) and `Event Statuses` (e.g., `COMPLETED`) using dictionaries defined in Google Sheets.
- Non-US articles are logged to the `Ontology Review` tab for continuous learning.

## 5. Rules Engine (Multi-Channel Scoring)
The `src/rules_engine.py` evaluates all independent evidence channels (Ontology, Document Type, Source Reliability) to establish a **Base Score**.
- It then evaluates specific rules, adding points for Keywords or Modifiers.
- **Filtering:** If a rule specifies a required Semantic Concept and the article doesn't have it, the rule is skipped.
- **Threshold:** If the final score exceeds the threshold (e.g., 10 points), the article proceeds.

## 6. AI Target Extraction & Verification
The system calls Google Gemini (or OpenRouter) to extract the primary **Ticker Symbol** from the text.
- If the ticker is private, or if options are required but not available (via `yfinance`), the article is dropped.

## 7. AI Event Classification
The system uses the AI to officially classify the event family.
- If the AI flags it as a "False Positive", it is dropped.
- If the AI is unsure, it is flagged as an "Unknown Event" and logged for human review.

## 8. AI Research & Playbook Execution
The specific `Playbook` (prompt template) for the classified event is loaded from Google Sheets, alongside a `Gold Standard` historical example.
- The AI reads the entire article, financial market data (from `yfinance`), and the Playbook to draft a structured Investment Memo.

## 9. Final Deduplication (Daily Memory)
Before sending the alert, the system checks the `Daily Memory` tab in Google Sheets.
- If the same issuer has already generated a successful alert today (e.g., from syndicated news crossing wires at the same time), the article is dropped to prevent email spam.

## 10. Alerts & Archiving
- An email alert is dispatched to the user.
- The article is committed to the SQLite database.
- The issuer is added to the Daily Memory.
- Operational metrics are logged.
