# SSR Workbook Specification

The Google Sheet is the operational control center of SSR. It allows non-technical portfolio managers to control the Python pipeline without touching code.

## 1. Rules Tab
The core logic matrix that defines what SSR cares about.
- **Event Family:** The high-level classification (e.g., `Cash Merger`, `Spin-off`).
- **Keyword:** The specific regex/string to search for.
- **Score:** Points awarded if the keyword is found (e.g., `10`). Threshold is typically 10 or 15.
- **Exclusions:** Rule-specific exclusions (e.g., ignore the word `SPAC` only for the Cash Merger rule).
- **AI Prompt:** Custom instructions injected into the AI's Research Engine to train it on edge cases for this specific Event Family (e.g., "Return False Positive if this is a rumor").

## 2. Global Exclusions Tab
The universal blacklist.
- A simple list of words, phrases, or PR firms.
- If ANY of these exist in the title or body of a scraped article, the Python engine drops the article instantly before spending API credits.

## 3. Playbooks Tab
Specific research questions for the AI.
- **Event Family:** Matches the rule tab.
- **Questions:** Custom diligence questions the AI must answer during "Case Research" (e.g., "What is the premium?", "Are there specific regulatory hurdles mentioned?"). These are dynamically injected into the Investment Memo.

## 4. Sources Tab
Tracks ingestion performance.
- **Source Name:** e.g., `PR Newswire` or `SEC EDGAR`.
- **URL:** The RSS feed or HTML path.
- **Last Checked:** Timestamp updated by Python.
- **Articles Scraped:** Volume tracking.

## 5. AI Research Queue
A historical log of processed events for human auditing.
- Python appends rows here containing the URL, the Event Family, and the raw AI reasoning, allowing humans to easily review why an event was flagged.
