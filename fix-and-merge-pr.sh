#!/usr/bin/env bash
set -euo pipefail

REPO="tonyfonda-eng/SSR"
PR_NUMBER="11"
BRANCH="feature/deploy-settings"
BASE_BRANCH="main"
REMOTE="origin"

echo "Repository: $REPO"
echo "PR: #$PR_NUMBER"
echo "Branch: $BRANCH"

command -v git >/dev/null 2>&1 || { echo "git is required. Aborting."; exit 2; }
command -v gh >/dev/null 2>&1 || { echo "gh (GitHub CLI) is required. Aborting."; exit 2; }

if ! gh auth status >/dev/null 2>&1; then
  echo "gh is not authenticated. Run 'gh auth login' first."
  exit 2
fi

git fetch $REMOTE --prune
git fetch $REMOTE "$BASE_BRANCH":"refs/remotes/$REMOTE/$BASE_BRANCH" || true

if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
  git checkout "$BRANCH"
  git reset --hard "$REMOTE/$BRANCH" || true
else
  git checkout -B "$BRANCH" "$REMOTE/$BRANCH"
fi

echo "Attempting rebase onto $BASE_BRANCH..."
set +e
git rebase "$REMOTE/$BASE_BRANCH"
REBASE_EXIT=$?
set -e

if [[ $REBASE_EXIT -eq 0 ]]; then
  echo "Rebase succeeded. Pushing branch..."
  git push --force-with-lease $REMOTE "$BRANCH"
else
  echo "Rebase failed with conflicts. Attempting auto-resolve with 'theirs'..."
  git rebase --abort || true
  git merge "$REMOTE/$BASE_BRANCH" -X theirs --no-edit
  git push $REMOTE "$BRANCH"
fi

echo "Reopening PR #$PR_NUMBER..."
gh pr reopen "$PR_NUMBER" --repo "$REPO" || true

echo "Merging PR #$PR_NUMBER..."
gh pr merge "$PR_NUMBER" --repo "$REPO" --merge --delete-branch
echo "Done!"
