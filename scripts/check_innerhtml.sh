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
