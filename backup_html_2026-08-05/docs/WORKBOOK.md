# Workbook Schema

The Special Situations Radar system is entirely driven by a single Google Sheets Workbook. This workbook acts as the central Knowledge Base, allowing non-technical analysts to modify business logic, add sources, and tweak AI prompts without touching Python code.

## Configuration Tabs

### 1. Settings
*   **Purpose:** Defines global operational parameters (e.g., drift thresholds, maximum runtime, dashboard publish intervals).
*   **Engine Interaction:** Fetched on startup to control pipeline health metrics.

### 2. Sources
*   **Purpose:** The central registry for all news feeds.
*   **Engine Interaction:** Defines whether a source is HTML or RSS, its language/country context, its base reliability score, and whether it is actively polled.

### 3. Global Exclusions
*   **Purpose:** A "Kill Switch" list of regex phrases.
*   **Engine Interaction:** Any article containing these phrases is instantly dropped and permanently archived *before* AI processing.

## Ontology & Rules Tabs

### 4. Semantic Concepts
*   **Purpose:** Translates foreign keywords and synonyms into abstract concepts (e.g., `ACQUISITION`).
*   **Engine Interaction:** Grants points to the article if any keyword in any mapped language is detected.

### 5. Event Status
*   **Purpose:** Translates deal stages (e.g., `COMPLETED`, `RUMOUR`).
*   **Engine Interaction:** Adds or subtracts points based on the stage of the deal. Often used to mathematically kill deals that have already closed.

### 6. Document Types
*   **Purpose:** Scores the reliability of specific filing types (e.g., `8-K`, `Form 4`).
*   **Engine Interaction:** Adds points to the Base Score.

### 7. Rules
*   **Purpose:** The core decision engine mapping evidence to specific Cash Event triggers.
*   **Engine Interaction:** Uses the Base Score (from Ontology, Source, Document) and evaluates it against rule-specific keywords, confidence modifiers, and semantic concept requirements. Articles that pass the threshold proceed to AI analysis.

### 8. Playbooks
*   **Purpose:** The AI prompt templates.
*   **Engine Interaction:** Injected directly into Google Gemini/OpenRouter to structure the final Investment Memo.

### 9. AI Gold Standards
*   **Purpose:** Provides the AI with a perfectly analyzed historical example.
*   **Engine Interaction:** Included in the system prompt for few-shot learning to ensure output consistency.

## Monitoring & Logs

### 10. AI Research Queue
*   **Purpose:** A human-readable log of all successfully generated Investment Memos.

### 11. Unknown Events
*   **Purpose:** Logs any article that triggered a rule but could not be confidently classified by the AI.

### 12. Ontology Review
*   **Purpose:** A continuous learning feed. Logs all non-US articles and the exact terms detected to help analysts refine the `Semantic Concepts` translations.

### 13. Daily Memory
*   **Purpose:** An ephemeral cache of all issuers successfully alerted on today. Prevents syndicated news storms from generating duplicate emails on the same day.

### 14. Statistics & Health
*   **Tabs:** `Daily Statistics`, `AI Usage`, `Source Statistics`, `Workflow Health`
*   **Purpose:** Aggregated operational metrics pushed by the system for long-term health tracking.
