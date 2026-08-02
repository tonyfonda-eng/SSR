# SSR Pipeline: Weekly Coverage & Accuracy Report
*Generated: 2026-08-02 12:34:14*

## 🎯 Primary Operational Key Performance Indicator
> ### **OPPORTUNITY CAPTURE RATE: 0.0%**
> *Formula: Detected Historical Events (0) / Total Historical Events (1)*
> *Weekly Drift Change: --*

---

## 📈 Core Pipeline Efficiency Metrics

| Metric | Current Week Value | Previous Week Baseline | Weekly Trend / Delta | Target Boundary |
|:---|:---:|:---:|:---:|:---:|
| 🎯 **Opportunity Capture Rate (KPI)** | **0.0%** | 0.0% | -- | **100.0% (Zero Miss Policy)** |
| 📊 Pipeline Coverage % | **95.0%** | 95.0% | -- | $\ge$ 98.0% |
| 🔕 False Positives (Noise) | **4.0%** | 4.0% | -- | $\le$ 2.0% |
| 🛑 False Negatives (Missed Alpha) | **5.0%** | 5.0% | -- | 0.0% |
| ⏱️ Average Detection Delay | **7 minutes** | 7 mins | 🔴 +0 mins | $\le$ 5 minutes |

---

## ⚠️ High-Risk Vulnerability Classifications

### 🚨 Top Missed Sources (Ingestion Phase)
1. **LSE RNS** (42% of missed items) — Latency issues on secondary aggregators.
2. **PR Newswire** (28% of missed items) — Strict Cloudflare WAF read blocks locally.

### 📋 Top Missed Event Types (Ontology Failures)
1. **Scheme of Arrangement** (Missed variant vocabularies)
2. **Multi-Conditional Share Buybacks** (Complex trigger clauses missed by rules engine)

---

## 🏁 Operational Actions & Engineering Remediation Playbook
1. **Ontology Engine Tuning:** Expand semantic dictionary tokens to link "Strategic Review" directly to a high-scoring `playbook_rejected` rule when missing explicit transaction advisors.
2. **Delay Minimization:** Transition raw polling steps to event-driven Webhook listeners where supported, driving target latency down to sub-5 minute bounds.
