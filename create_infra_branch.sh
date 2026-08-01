#!/usr/bin/env bash
set -euo pipefail

echo "[INFO] Creating and switching to branch: infra/secret-scanning"
git checkout -b infra/secret-scanning

echo "[INFO] Creating directories..."
mkdir -p .github/workflows scripts tools docs

echo "[INFO] Writing .github/workflows/secret-scan.yml..."
cat > .github/workflows/secret-scan.yml <<'YML'
name: Secret scan

on:
  push:
    branches: [ main ]
  pull_request:

jobs:
  gitleaks:
    name: Gitleaks secret scan
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Run gitleaks (detect secrets)
        uses: zricethezav/gitleaks-action@v2
        with:
          args: detect --source . --report-format json --report-path gitleaks-report.json --redact

      - name: Upload report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: gitleaks-report
          path: gitleaks-report.json
YML

echo "[INFO] Writing .pre-commit-config.yaml..."
cat > .pre-commit-config.yaml <<'YML'
repos:
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.3.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: check-added-large-files
        args: [--maxkb=5000]
  - repo: local
    hooks:
      - id: check-innerhtml
        name: Check for innerHTML usages
        entry: scripts/check_innerhtml.sh
        language: script
        files: '\.(js|jsx|ts|tsx|html)$'
        types: [file]
YML

echo "[INFO] Writing scripts/check_innerhtml.sh..."
cat > scripts/check_innerhtml.sh <<'SH_INNER'
#!/usr/bin/env bash
set -euo pipefail

pattern='innerHTML'
if command -v rg >/dev/null 2>&1; then
  matches=$(rg --hidden --no-ignore-vcs --glob '!node_modules' -n --type-add 'web:*.{js,jsx,ts,tsx,html}' -tweb "$pattern" || true)
else
  matches=$(grep -RIn --exclude-dir={.git,node_modules,build,dist,venv,.venv} --include=*.{js,jsx,ts,tsx,html} "$pattern" . || true)
fi

if [[ -n "$matches" ]]; then
  echo "Found uses of 'innerHTML' (potential XSS vectors). Please review and replace with safe DOM APIs:"
  echo
  echo "$matches"
  echo
  exit 1
fi
exit 0
SH_INNER
chmod +x scripts/check_innerhtml.sh

echo "[INFO] Writing tools/run_secret_scan.sh..."
cat > tools/run_secret_scan.sh <<'SH_TOOL'
#!/usr/bin/env bash
set -euo pipefail

REPORT="gitleaks-report.json"
if command -v gitleaks >/dev/null 2>&1; then
  echo "Running gitleaks binary..."
  gitleaks detect --source . --report-path "$REPORT" --redact
  echo "Report saved to $REPORT"
  exit 0
fi

if command -v docker >/dev/null 2>&1; then
  echo "gitleaks binary not found — running via Docker..."
  docker run --rm -v "$(pwd)":/src -w /src zricethezav/gitleaks:latest detect --source . --report-path "$REPORT" --redact
  echo "Report saved to $REPORT"
  exit 0
fi

echo "Please install gitleaks (https://github.com/zricethezav/gitleaks) or Docker to run the scan."
exit 2
SH_TOOL
chmod +x tools/run_secret_scan.sh

echo "[INFO] Writing docs/SECURITY.md..."
cat > docs/SECURITY.md <<'MD'
# Security & Secrets Handling

This document explains how the repository handles secrets and what to do if a secret is accidentally committed.

## Automated scanning
- A GitHub Action (`.github/workflows/secret-scan.yml`) runs Gitleaks on pushes and PRs, failing CI on high-confidence findings.
- A pre-commit hook (`detect-secrets`) is recommended for local developer checks.

## If a secret is discovered in the repository
1. Treat the secret as compromised immediately.
2. Rotate the secret (revoke and create a replacement) in the issuing service.
3. Remove the secret from the repository and history using tools like `git filter-repo` or BFG. Coordinate with collaborators before force-pushing history rewrites.

## Contact & escalation
If you find a leaked secret, open an issue in this repository and tag the repository owners/ops team.
MD

echo "[INFO] Staging and committing files..."
git add .github/workflows/secret-scan.yml .pre-commit-config.yaml scripts/check_innerhtml.sh tools/run_secret_scan.sh docs/SECURITY.md
git commit -m "ci(security): add gitleaks secret-scan workflow, pre-commit hooks, and scan utilities"

echo "[INFO] Pushing branch to origin..."
git push -u origin infra/secret-scanning

echo "[SUCCESS] Batch step 1 complete. Branch pushed successfully."
