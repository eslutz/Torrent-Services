#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "ERROR: Not inside a git repository: $repo_root" >&2
  exit 1
fi

git config core.hooksPath .githooks

chmod +x .githooks/pre-commit

echo "Installed git hooks path: $(git config core.hooksPath)"
echo "Pre-commit hook: .githooks/pre-commit"
