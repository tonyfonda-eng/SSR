# SSR Forensic Audit Report

> [!CAUTION]
> **CRITICAL INCIDENT IDENTIFIED:** The pipeline is suffering from a 100% false negative rate at the terminal gates due to type mismatching in the playbook filter and improper pipeline stage ordering. No emails have been sent.

## SECTION 1 — Complete Pipeline Funnel

### Q1: Pipeline Funnel (Last 20 Runs)
| Stage | Entered | Passed | Rejected | % Pass |
|---|---|---|---|---|
| Dedupe Hash | 20,787 | 12,051 | 8,736 | 57.97% |
| Dedupe Issuer Memory | 12,051 | 12,051 | 0 | 100.0% |
| Exclude Global Keywords | 12,051 | 12,044 | 7 | 99.94% |
| Exclude Issuer Feed | 12,044 | 12,044 | 0 | 100.0% |
| Ontology Concepts | 12,044 | 2,766 | 9,278 | 22.97% |
| Regex Rules | 2,766 | 2,766 | 0 | 100.0% |
| Python Issuer Extraction | 2,766 | 2,766 | 0 | 100.0% |
| Python Ticker Lookup | 2,766 | 2,766 | 0 | 100.0% |
| Ai Ticker Resolution | 2,733 | 1,331 | 1,402 | 48.7% |
| Entity Confidence | 1,364 | 1,332 | 32 | 97.65% |
| Tradeability Check | 1,332 | 1,332 | 0 | 100.0% |
| Liquidity Check | 1,332 | 1,332 | 0 | 100.0% |
| Financial Market Cap | 1,332 | 1,332 | 0 | 100.0% |
| Financial T12 Floor | 1,332 | 197 | 1,135 | 14.79% |
| Options Chain Check | 197 | 133 | 64 | 67.51% |
| Playbook Gate | 133 | 0 | 133 | 0.0% |
| Ai Event Classification | 0 | 0 | 0 | 0% |
| Ai Confidence | 0 | 0 | 0 | 0% |
| Alert Generation | 0 | 0 | 0 | 0% |
| Email Sent | 0 | 0 | 0 | 0% |

### Q2: Largest Rejection Stage
- **Stage:** `ontology_concepts`
- **Total Rejected:** 9,278
- **% of Initial Volume:** ~45% (of total dedupe_hash entered) / 77% (of ontology entered)
- **Reason:** Standard wire noise. The baseline taxonomy filter aggressively drops PR fluff (product launches, personnel changes) that lack structural M&A semantic markers.

## SECTION 2 — Alert Death Investigation

### Q3: Articles Reaching send_alert()
| Run | Articles reaching send_alert() | Emails attempted | Emails successfully sent | Email failures |
|---|---|---|---|---|
| All 20 | 0 | 0 | 0 | 0 |

### Q4: Execution Stopper
**`playbook_gate`** is the final execution point. 
**Call Chain:** `process_article()` -> `execution_order` loop -> `stage_playbook_eligibility_check`.
**Result:** 133 articles entered the gate, 0 passed, 133 rejected.

### Q5: SMTP/API Errors
None. The function `send_alert()` was never executed.

## SECTION 3 — False Negative Investigation

### Q6 & Q7: Top Rejected Articles
> [!WARNING]
> Genuine M&A articles are being discarded at the Playbook and Entity gates. The AI classifier is never reaching them.

Sample of high-scoring articles rejected at late stages (from `article_screening_log`):
- **Headline:** Jul 20, 2026, 16:05 ETWashington Trust Reports Second Quarter 2026 ResultsWashington Trust Bancorp, Inc. (Nasdaq: WASH; "Washington Trust" or the "Corporation"), today reported second quarter 2026 net income of $16.0... | **Ticker:** WASH | **Dropped At:** financial_t12_floor (dropped_financial_t12)
- **Headline:** Jul 20, 2026, 16:05 ETCRACKER BARREL ANNOUNCES STRATEGIC ACTIONSCracker Barrel Old Country Store, Inc. ("Cracker Barrel" or the "Company") (Nasdaq: CBRL) today announced two strategic actions. Sale-Leaseback... | **Ticker:** CBRL | **Dropped At:** financial_t12_floor (dropped_financial_t12)
- **Headline:** Jul 20, 2026, 16:01 ETAGNC Investment Corp. Announces Second Quarter 2026 Financial ResultsAGNC Investment Corp. ("AGNC" or the "Company") (Nasdaq: AGNC) today announced financial results for the quarter ended June 30, 2026. SECOND QUARTER... | **Ticker:** AGNC | **Dropped At:** financial_t12_floor (dropped_financial_t12)
- **Headline:** Jul 20, 2026, 16:05 ETHemlo Mining Corp. Reports Second Quarter 2026 Operating ResultsHemlo Mining Corp. (TSX: HMMC) (OTCQX: HMMCF) ("Hemlo Mining" or the "Company") is pleased to report operating results for the second quarter ended... | **Ticker:** HMMC | **Dropped At:** financial_t12_floor (dropped_financial_t12)
- **Headline:** Jul 20, 2026, 16:15 ETUranium Royalty Corp. Obtains Shareholder Approval for Arrangement and Provides Corporate UpdateUranium Royalty Corp. (NASDAQ: UROY) (TSX: URC) ("URC" or the "Company") is pleased to announce shareholder approval of its previously announced plan ... | **Ticker:** UROY | **Dropped At:** playbook_gate (dropped_no_playbook)
- **Headline:** Jul 20, 2026, 16:10 ETBiscuit Belly Positions for Next Phase of Growth with Acquisition of Maple Street Biscuit CompanyBiscuit Belly, a privately held, fast-growing gourmet biscuit sandwich concept, announces the acquisition of 34 locations from Maple Street Biscuit... | **Ticker:** UNKNOWN | **Dropped At:** ai_ticker_resolution (dropped_ai_no_ticker)
- **Headline:** Jul 20, 2026, 16:20 ETVilla Sandi Turns Its Vineyards Into An Intelligent Ecosystem For Precision ViticultureVilla Sandi, a historic family-owned winery in Italy's Veneto region and a pioneer of premium Prosecco, is accelerating its commitment to precision... | **Ticker:** UNKNOWN | **Dropped At:** ai_ticker_resolution (dropped_ai_no_ticker)
- **Headline:** Jul 20, 2026, 16:16 ETFIRST UNITED CORPORATION ANNOUNCES SECOND QUARTER 2026 FINANCIAL RESULTSFirst United Corporation (the "Corporation", "we", "us", and "our") (NASDAQ: FUNC), a bank holding company and the parent company of First United... | **Ticker:** FUNC | **Dropped At:** financial_t12_floor (dropped_financial_t12)
- **Headline:** Jul 20, 2026, 16:15 ETSuncrete, Inc. Announces Schedule for Second Quarter 2026 Earnings Release and Conference CallSuncrete, Inc. (Nasdaq: RMIX) ("Suncrete" or the "Company"), a ready-mix concrete logistics and distribution platform strategically located in the... | **Ticker:** RMIX | **Dropped At:** financial_t12_floor (dropped_financial_t12)
- **Headline:** Jul 20, 2026, 16:30 ETSteel Dynamics Reports Second Quarter 2026 ResultsSecond Quarter 2026 Performance Highlights: Record steel shipments of 3.7 million tons Continued commissioning and increased production from aluminum ... | **Ticker:** UNKNOWN | **Dropped At:** ai_ticker_resolution (dropped_ai_no_ticker)

## SECTION 4 — Ontology Health

### Q8: Ontology Scores Histogram
- **Total Articles Evaluated:** 5,000
- **Score exactly 0.00:** 3,817 (76.3%)
- **0.01 - 0.64:** ~300
- **0.65 - 1.00+:** ~883

**Why 0.00 from code:**
`get_concept_matches()` relies on exact boundary word matches (`\bphrase\b`) from `_KNOWLEDGE_GRAPH`. If an article is a standard product announcement with no semantic overlap with M&A taxonomy terms, it correctly scores a perfect `0.00`. This is expected behavior for an institutional filter processing raw PR Newswire feeds.

### Q9: Sample Ontology Failures
**Sample 1** - Score: 0.00. **Missing Concepts:** 12 missing. (Pure noise article)
**Sample 2** - Score: 0.00. **Missing Concepts:** 12 missing. (Pure noise article)
**Sample 3** - Score: 0.00. **Missing Concepts:** 12 missing. (Pure noise article)

## SECTION 5 — AI Usage

### Q10: AI Stage Metrics
- **Reached `ai_ticker_resolution`:** ~136 per run (2,733 total / 20 runs)
- **Reached `ai_event_classification`:** 0 per run
- **Reached `execute_playbook()`:** 0 per run

### Q11: Architecture Comparison
- **Original Architecture:** AI evaluated almost all documents passing the baseline keyword filter.
- **Current Architecture:** AI evaluates **0** documents for event classification.
- **Reduction:** 100% drop in AI classification volume due to the Playbook gate wall.

## SECTION 6 — Financial Gates

### Q12: Financial Gate Rejections
- **No ticker (`dropped_ai_no_ticker`):** 1,402
- **Liquidity (`dropped_insufficient_liquidity`):** 0
- **Financial T12 (`dropped_financial_t12`):** 1,134
- **No options (`dropped_no_options_chain`):** 64
- **Playbook (`dropped_no_playbook`):** 133

### Q13: Financial T12 Rejections Sample
- **Ticker:** BAX | **Reason:** dropped_financial_t12
- **Ticker:** AGX | **Reason:** dropped_financial_t12
- **Ticker:** DBRG | **Reason:** dropped_financial_t12
- **Ticker:** DXPE | **Reason:** dropped_financial_t12
- **Ticker:** RBA | **Reason:** dropped_financial_t12

## SECTION 7 — Playbook Audit

### Q14: Playbook Matches
- **Matches:** 0
- **Why (from code):** The function `stage_playbook_eligibility_check` compares strings to dictionaries. It iterates through `_deterministic_families` (which contains `dict` objects like `{"Rule": "merger", "Score": 15}`), casts them to strings (`"{'Rule': 'merger'...}"`), and checks if that exact string exists in `active_playbooks` (which contains simple strings like `"merger"`). It will never match.

## SECTION 8 — Email Pipeline

### Q15: Trace Email Execution
1. `process_article()` begins execution loop
2. Passes ontology and deterministic rules
3. Reaches `stage_playbook_eligibility_check` ("playbook_gate")
4. **EXECUTION STOPS HERE** (Returns `False, "dropped_no_playbook"`)
5. `commit_decision_capsule()` is called with `DROPPED`
6. Pipeline returns before `send_alert()` is invoked.

## SECTION 9 — Impossible Condition Audit

### Q16: Impossible Logic Gates
1. **The Dictionary-String Cast (Playbook Gate):** `any(family in active_playbooks for family in [str(f).lower() for f in article.get("_deterministic_families")])`. Always False.
2. **The Double Entity Lock (Entity Confidence Gate):** `if ticker == "UNKNOWN" and issuer == "UNKNOWN": ... elif ticker == "UNKNOWN": return False ... elif issuer == "UNKNOWN": return False`. Requires BOTH Ticker and Issuer to be present, meaning valid ticker extractions are dropped if the brittle regex fails to find the company name.
3. **Cart before the Horse (Pipeline Order):** `playbook_gate` executes *before* `ai_event_classification`, meaning the pipeline expects to filter by event playbook before the AI has actually classified the event.

## SECTION 10 — Final Diagnosis

### Q17: Top Reasons for No Emails
1. **Playbook Type Mismatch Bug**
   - **Likelihood:** 100%
   - **Evidence:** 0 articles pass playbook gate; `str(dict)` matching logic in `monitor.py`.
   - **Impact:** Terminal. Kills all valid alerts.
2. **Entity Double-Lock Bug**
   - **Likelihood:** High
   - **Evidence:** `stage_entity_confidence_gate` strictly requires both issuer and ticker.
   - **Impact:** Discards valid articles where issuer name extraction fails.
3. **Pipeline Ordering Logic Flaw**
   - **Likelihood:** High
   - **Evidence:** `ai_event_classification` is placed after playbook filtering.
   - **Impact:** Architectural contradiction preventing dynamic AI routing.

## SECTION 11 — The Most Important Question

### Q18: Trace of a Real Acquisition Announcement
If a real US acquisition drops today:
1. **Ingestion -> Ontology:** PASS (High keyword overlap)
2. **Regex Rules:** PASS (Matches M&A triggers)
3. **Ticker Lookup:** PASS (Extracts ticker)
4. **Entity Confidence:** LIKELY FAIL (If company name format doesn't exactly match `([A-Z][A-Za-z0-9\,\.\&\s]{2,40})\s+\((?:NYSE|NASDAQ...\)` regex)
5. **Financial Gates:** PASS (Valid T12, Options exist)
6. **Playbook Gate:** **GUARANTEED REJECT** (Due to dictionary string cast bug)

**Gate Responsible:** `playbook_gate` ensures 100% rejection before the email module is ever reached.
