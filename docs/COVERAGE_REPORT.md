# SSR Pipeline: Weekly Coverage & Accuracy Report
*Generated: 2026-08-02 12:01:17*

This report aggregates automated coverage verification and manual VQA checklist metrics over the current trading week cycle. Performance targets focus on minimizing **Detection Delay** and eliminating leakage within the **Ontology Engine**.

---

## 📈 Core Pipeline Efficiency Metrics

| Metric | Current Week Value | Previous Week Baseline | Weekly Trend / Delta | Target Boundary |
|:---|:---:|:---:|:---:|:---:|
| **Pipeline Coverage %** | **95.0%** | 93.5% | 🟢 +1.5% | $\ge$ 98.0% |
| **False Positives (Noise)** | **4.0%** | 5.2% | 🟢 -1.2% | $\le$ 2.0% |
| **False Negatives (Missed Alpha)** | **5.0%** | 6.5% | 🟢 -1.5% | 0.0% (Zero Leakage) |
| **Average Detection Delay** | **7 minutes** | 9 mins | 🟢 -2 mins | $\le$ 5 minutes |

---

## ⚠️ High-Risk Vulnerability Classifications

### 🚨 Top Missed Sources (Ingestion Phase)
1. **LSE RNS** (42% of missed items) — Latency issues on secondary aggregators.
2. **PR Newswire** (28% of missed items) — Strict Cloudflare WAF read blocks locally.
3. **ASX Announcements** (18% of missed items) — Parsing variances during regional off-hours.

### 📋 Top Missed Event Types (Ontology Failures)
1. **Scheme of Arrangement** (Missed variant vocabularies)
2. **Multi-Conditional Share Buybacks** (Complex trigger clauses missed by rules engine)
3. **M&A Asset Disposals** (Misclassified as standard operational updates)

---

## 🔧 Rule Performance & Scoring Optimization Profiles

### 🔴 Top False Negative Rules (Too Strict / Dropped Signals)
- `Rule_Ontology_Core_Buyback`: Failed to capture "Repurchase Offer" syntax alternatives.
- `Rule_Market_Cap_Floor`: Erroneously filtered out micro-cap dual-listings with complex quote formats.

### 🟡 Top False Positive Rules (Too Loose / Created Noise)
- `Rule_Strategic_Alternatives_Review`: Consistently flagged standard corporate board reshuffles lacking explicit liquidation intent.
- `Rule_Tender_Offer_Keywords`: Triggered broadly on preliminary debt-refinancing disclosures rather than equity events.

---

## 🏁 Operational Actions & Engineering Remediation Playbook
1. **Ontology Engine Tuning:** Expand semantic dictionary tokens to link "Strategic Review" directly to a high-scoring `playbook_rejected` rule when missing explicit transaction advisors.
2. **Delay Minimization:** Transition raw polling steps to event-driven Webhook listeners where supported, driving target latency down to sub-5 minute bounds.
