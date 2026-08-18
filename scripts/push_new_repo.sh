#!/usr/bin/env bash
# After you create an empty public repo named ti15-playoff-analyzer:
#   bash scripts/push_new_repo.sh
set -euo pipefail
REMOTE="${1:-https://github.com/Justineya/ti15-playoff-analyzer.git}"
DEST="${TMPDIR:-/tmp}/ti15-playoff-analyzer-push"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
rm -rf "$DEST"
mkdir -p "$DEST"
cp -a "$ROOT"/. "$DEST/"
rm -rf "$DEST/data/cache" "$DEST/web/.netlify" "$DEST/.wrangler" "$DEST/.git"
find "$DEST" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
cd "$DEST"
git init -b main
git add -A
git -c user.email="ti15@local" -c user.name="ti15" commit -m "Initial TI15 playoff analyzer with unattended refresh."
git remote add origin "$REMOTE"
git push -u origin main
echo "pushed $REMOTE"
