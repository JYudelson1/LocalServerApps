#!/usr/bin/env bash
# download.sh — bootstrap or refresh this server.
#   1. ensure git is installed
#   2. ensure uv is installed
#   3. pull the parent repo + submodules to latest
#   4. bring up services via the automation control plane (ctl.py) so we never
#      double-start anything — launchd/systemd own the lifecycle.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

OS="$(uname -s)"

# --- 1. git ---------------------------------------------------------------
if ! command -v git >/dev/null 2>&1; then
  echo "git not found; installing…"
  case "$OS" in
    Darwin)
      if command -v brew >/dev/null 2>&1; then
        brew install git
      else
        echo "Install the Xcode command line tools first: xcode-select --install" >&2
        exit 1
      fi ;;
    Linux)
      sudo apt-get update && sudo apt-get install -y git ;;
    *) echo "Unsupported OS for auto-install: $OS" >&2; exit 1 ;;
  esac
fi

# --- 2. uv ----------------------------------------------------------------
if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found; installing…"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # uv lands in ~/.local/bin (or ~/.cargo/bin); make it visible for this run.
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi

# --- 3. pull latest -------------------------------------------------------
if [ -d .git ]; then
  git pull
  "$ROOT/update_submodules.sh"
else
  echo "Not a git checkout; skipping pull."
fi

# --- 4. bring services up via the control plane ---------------------------
# enable admin-panel: guarantees the panel is on even on a brand-new server
# (a fresh runtime.json starts everything disabled). apply: reconcile the rest
# of THIS server's runtime state (restored from backup, if any).
python3 "$ROOT/automation/ctl.py" enable admin-panel
python3 "$ROOT/automation/ctl.py" apply

echo
echo "Server up. Services are managed via automation/ctl.py (and the admin panel)."
echo "Reminder: place the shared secrets file at $ROOT/.env"
