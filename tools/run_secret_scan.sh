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
