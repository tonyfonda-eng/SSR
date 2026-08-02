# SSR Complete System Call Hierarchy
*Document Version: 1.0.0 (Production Structural Map)*

This document provides a comprehensive, unlimited-depth call hierarchy starting from the root orchestrator `monitor.py`. It explicitly maps every function, method, class, and cross-module dependency across the Special Situations Radar codebase.

---

## 🌳 Root Entry Point: `monitor.py`

```text
monitor.py [Module]
 └── main() [Function]
      ├── sqlite3.connect() [External StdLib Method]
      │    └── sqlite3.Connection [Class]
      │         └── cursor() [Method]
      ├── load_issuer_cache() [Function - Cross-Module / Google Sheets API]
      │    └── googleapiclient.discovery.build() [External Library Method]
      │         └── spreadsheets().values().get() [API Method Call]
      ├── load_ontology_rules() [Function - Cross-Module / Regex Engine]
      │    └── re.compile() [External StdLib Method]
      │         └── re.Pattern [Class]
      ├── [Loop] poll_scraper(scraper_name) [Function - Ingestion Matrix]
      │    └── requests.get() [External Library Method]
      │         └── Response [Class]
      │              └── json() / text [Method]
      ├── evaluate_deduplication(article_key) [Function - Persistence Check]
      │    └── sqlite3.Cursor.execute() [Method]
      │         └── fetchone() [Method]
      ├── evaluate_ontology(title, body) [Function - Semantic Matching]
      │    └── re.Pattern.search() [Method]
      ├── evaluate_playbook_rules(article_data) [Function - Quantitative Scoring]
      │    └── calculate_metric_thresholds() [Internal Function]
      ├── invoke_llm_analysis(payload) [Function - AI Gateway]
      │    └── requests.post() / OpenAI SDK client.chat.completions.create() [External API Call]
      └── dispatch_alert(alert_payload) [Function - Dispatch Layer]
           └── smtplib.SMTP / requests.post() [External Transport Method]
eof
