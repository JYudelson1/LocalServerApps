#!/usr/bin/env bash
# Initialize and update all submodules to the latest commit on each tracked branch.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

usage() {
  cat <<'EOF'
Usage: ./update_submodules.sh

Fetches and checks out the latest commit on each submodule's tracked branch
(see branch= in .gitmodules). Safe to run after cloning or when child repos
have new pushes.

Steps:
  git submodule sync --recursive
  git submodule update --init --recursive --remote
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -gt 0 ]]; then
  echo "Error: unknown option: $1 (try --help)" >&2
  exit 1
fi

git rev-parse --git-dir >/dev/null 2>&1 \
  || { echo "Error: run this from the LocalServerApps git repo root" >&2; exit 1; }

if [[ ! -f .gitmodules ]]; then
  echo "No submodules configured (.gitmodules missing)."
  exit 0
fi

echo "Syncing submodule URLs from .gitmodules..."
git submodule sync --recursive

echo "Updating submodules (init + latest on tracked branches)..."
git submodule update --init --recursive --remote

echo
echo "Submodule status:"
git submodule status
