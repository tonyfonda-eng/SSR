# Changelog

All notable changes to the Special Situations Radar system will be documented in this file.

## 2026-08-01

### Added
*   **Living Documentation Pipeline:** Automatically builds HTML manuals and SVG diagrams from Markdown files in `/docs` using GitHub Actions and GitHub Pages.
*   **AI Circuit Breakers:** Gracefully aborts ingestion loops when Gemini or OpenRouter hit hard quotas/exhaustion to save SQLite cache and prevent infinite timeouts.

### Changed
*   **Ontology Plugin Architecture:** Migrated from hardcoded English-only regex to a language-agnostic Semantic Concept and Event Status evaluation layer in `src/ontology`.
*   **GitHub Actions Deployment:** Added `permissions: contents: write` to CI workflow to allow automated publishing of the operational dashboard.

### Fixed
*   **Daily Memory Pruning:** Fixed bug preventing Google Sheets from correctly pruning the Daily Memory tab when there were fewer than 100 rows marked for deletion.
*   **BusinessWire Unblocking:** Transitioned back to RSS fallback logic to bypass 403 blocks during custom HTML scraper failures.

## 2026-07-31

### Added
*   **SQLite Deduplication Engine:** Shifted primary entity deduplication out of Google Sheets and into persistent SQLite tracking (`ssr_cache.sqlite`) for faster pipeline execution.
*   **Global Exclusions:** Implemented a new regex-based pre-filter kill switch to instantly drop noise based on the Google Sheets "Global Exclusions" tab.

### Removed
*   Legacy entity deduplication logic that was causing memory leaks and false positive drops.
