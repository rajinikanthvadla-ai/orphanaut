#!/usr/bin/env bash
# Enable repo git hooks (strips Cursor co-author from commit messages).
set -euo pipefail
cd "$(dirname "$0")/.."
git config core.hooksPath .githooks
chmod +x .githooks/prepare-commit-msg 2>/dev/null || true
echo "Git hooks enabled for this repo (.githooks/prepare-commit-msg)"
