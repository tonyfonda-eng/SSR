# AI Provider Audit Report
**Generated:** 2026-08-02 20:21:26 BST

## 1. Provider & Key Inventory
- **Gemini Pool**: Loaded (1 primary + 7 backups).
- **OpenRouter Pool**: Loaded (1 primary + 7 backups).
- **Total Registered Keys**: 16

## 2. Selection Flow & Call Path (Issuer Extraction)
```text
issuer.py (extract_issuing_company)
 ↓
ai.py (_generate_with_retry)
 ↓
ai.py (OpenRouter Pool) -> Model: google/gemini-2.0-flash-exp:free
 ↓
ai.py (Gemini Pool Fallback) -> Model: gemini-1.5-flash
