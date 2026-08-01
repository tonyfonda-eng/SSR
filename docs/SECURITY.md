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
