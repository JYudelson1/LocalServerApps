#!/usr/bin/env bash
# Pull the parent repo and update all submodules to latest on their tracked branches.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

git pull
"${ROOT}/update_submodules.sh"
