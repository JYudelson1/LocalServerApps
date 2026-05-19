#!/usr/bin/env bash
# Pull the parent repo and update all site submodules to latest on their tracked branches.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

git pull
git submodule update --init --recursive --remote

echo "Done. Sites:"
git submodule status
