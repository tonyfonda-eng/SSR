#!/bin/bash
set -e

echo "📦 Step 1: Navigating to project workspace..."
cd ~/special-situations-radar-main

echo "🔀 Step 2: Switching to the 'main' branch..."
git checkout main

echo "🔄 Step 3: Syncing local main with GitHub (downloading recent remote changes)..."
git pull origin main --rebase

echo "🛠️ Step 4: Grabbing our exact fixed files from your testing branch..."
git checkout testing-coderabbit -- src/ai.py src/database.py

echo "🚀 Step 5: Committing and pushing safely to main..."
git commit -m "fix(core): apply openrouter flash-latest and runtime schema patches" || echo "No changes to commit."
git push origin main

echo "✅ Git traffic jam resolved! The Claude patches are officially live on the main branch."
