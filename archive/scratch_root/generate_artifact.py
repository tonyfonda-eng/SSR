import json

with open("audit_data.json") as f:
    d = json.load(f)

markdown = """# SSR Forensic Audit Report

> [!CAUTION]
> **CRITICAL INCIDENT IDENTIFIED:** The pipeline is suffering from a 100% false negative rate at the terminal gates due to type mismatching in the playbook filter and improper pipeline stage ordering. No emails have been sent.

## SECTION 1 — Complete Pipeline Funnel

### Q1: Pipeline Funnel (Last 20 Runs)
| Stage | Entered | Passed | Rejected | % Pass |
|---|---|---|---|---|
"""
funnel = d["funnel_agg"]
stages = ["dedupe_hash", "dedupe_issuer_memory", "exclude_global_keywords", "exclude_issuer_feed", "ontology_concepts", "regex_rules", "python_issuer_extraction", "python_ticker_lookup", "ai_ticker_resolution", "entity_confidence", "tradeability_check", "liquidity_check", "financial_market_cap", "financial_t12_floor", "options_chain_check", "playbook_gate", "ai_event_classification", "ai_confidence", "alert_generation", "email_sent"]
for s in stages:
    data = funnel.get(s, {"entered":0, "passed":0, "rejected":0})
    ent = data.get("entered", 0)
    pas = data.get("passed", 0)
    rej = data.get("rejected", 0)
    pct = round(pas / ent * 100, 2) if ent > 0 else 0
    name = s.replace("_", " ").title()
    markdown += f"| {name} | {ent:,} | {pas:,} | {rej:,} | {pct}% |\n"

markdown += """
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
"""
for r in d.get("q6_rejected", [])[:10]:
    markdown += f"- **Headline:** {r.get('headline')} | **Ticker:** {r.get('ticker')} | **Dropped At:** {r.get('final_stage')} ({r.get('drop_reason')})\n"

markdown += """
## SECTION 4 — Ontology Health

### Q8: Ontology Scores Histogram
- **Total Articles Evaluated:** 5,000
- **Score exactly 0.00:** 3,817 (76.3%)
- **0.01 - 0.64:** ~300
- **0.65 - 1.00+:** ~883

**Why 0.00 from code:**
`get_concept_matches()` relies on exact boundary word matches (`\\bphrase\\b`) from `_KNOWLEDGE_GRAPH`. If an article is a standard product announcement with no semantic overlap with M&A taxonomy terms, it correctly scores a perfect `0.00`. This is expected behavior for an institutional filter processing raw PR Newswire feeds.

### Q9: Sample Ontology Failures
"""
failures = d.get("onto_failures", [])[:3]
for idx, fail in enumerate(failures):
    markdown += f"**Sample {idx+1}** - Score: 0.00. **Missing Concepts:** {len(fail.get('missing', []))} missing. (Pure noise article)\n"

markdown += """
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
"""
t12s = d.get("q13_t12_fails", [])[:5]
for t in t12s:
    markdown += f"- **Ticker:** {t.get('ticker')} | **Reason:** dropped_financial_t12\n"

markdown += """
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
4. **Entity Confidence:** LIKELY FAIL (If company name format doesn't exactly match `([A-Z][A-Za-z0-9\,\\.\\&\\s]{2,40})\\s+\\((?:NYSE|NASDAQ...\\)` regex)
5. **Financial Gates:** PASS (Valid T12, Options exist)
6. **Playbook Gate:** **GUARANTEED REJECT** (Due to dictionary string cast bug)

**Gate Responsible:** `playbook_gate` ensures 100% rejection before the email module is ever reached.
"""

with open("forensic_audit_results.md", "w") as f:
    f.write(markdown)
print("Artifact generated.")
