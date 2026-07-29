# SSR Development Roadmap

This document outlines the strategic progression of the Special Situations Radar from an intelligence engine into a complete Knowledge Base.

## The 15 Missing Systems to Build

1. **Explainability Engine (Completed):** Every alert must generate a structured "Trigger Summary" explaining exactly why it passed (Matched keywords, AI Confidence, Classification).
2. **Confidence Scoring:** Move beyond binary events. Score Rules confidence, AI confidence, Extraction confidence, and Overall confidence.
3. **Event Lifecycle Tracking:** One announcement is not one event. Follow the lifecycle from "Offer Announced" -> "Competing Bidder" -> "Regulator Approval" -> "Archived".
4. **Company Memory:** SSR should know the history. If Boeing has a new alert, SSR should already know its past spin-offs, activist campaigns, and historical alerts.
5. **Relationship Graph:** Connect entities (e.g., Apollo -> owns -> Company A -> bid for -> Company B).
6. **Event Deduplication (Completed):** If PR Newswire, Reuters, and SEC all report the same transaction, it should be logged as ONE case, not three separate alerts.
7. **Case Workspace:** Turn ephemeral emails into persistent workspaces with timelines, documents, SEC filings, and AI notes.
8. **Continuous AI Research:** Update research, confidence, and emails automatically as new documents hit the wire for an existing event.
9. **Research Gap Detection (Completed via Investment Memo):** AI explicitly lists what it *doesn't* know (e.g., Break fee, Expected close, Financing source).
10. **Analyst Question Generator (Completed via Investment Memo):** AI produces an "Analyst To-Do List" for the portfolio manager to investigate.
11. **Opportunity Ranking:** Score alerts 0-100 based on Premium, Spread, Liquidity, Probability, and Complexity so humans know what to read first.
12. **False Positive Learning:** When a human clicks "False positive", SSR learns from the mistake without requiring code changes.
13. **Research Notebook (Completed via DB Schema):** Store every AI run forever to compare the "First opinion" against the "Final outcome" to improve prompts over time.
14. **Outcome Database:** Log every completed deal (Closed, Failed, Higher bid, Final IRR) so SSR becomes its own training dataset.
15. **Strategy Analytics:** Track win rates, average premiums, average spreads, and holding periods grouped by sector, country, or AI prompt version to continuously improve strategy.
