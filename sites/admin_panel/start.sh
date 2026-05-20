#!/usr/bin/env bash
set -euo pipefail

PORT="${1:-8900}"

cd "$(dirname "$0")"

if ! command -v pgrep >/dev/null 2>&1; then
  echo "Error: pgrep is required to detect an already-running server" >&2
  exit 1
fi

running_pids=$(pgrep -f 'admin_panel\.main' 2>/dev/null || true)
if [[ -n "$running_pids" ]]; then
  echo "Error: admin_panel appears to be already running (this might be a mistake)." >&2
  echo "  PIDs: $(echo "$running_pids" | paste -sd ' ' -)" >&2
  echo "  To stop it and start fresh: pkill -f 'admin_panel.main'" >&2
  exit 1
fi

port_in_use() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    # iproute2 — default on Raspberry Pi OS / most Linux
    [[ -n $(ss -H -tln "sport = :$port" 2>/dev/null) ]]
  elif command -v lsof >/dev/null 2>&1; then
    # macOS and many Linux installs
    lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
  elif command -v fuser >/dev/null 2>&1; then
    # psmisc — common Debian/Pi fallback
    fuser "$port"/tcp >/dev/null 2>&1
  else
    echo "Error: need ss, lsof, or fuser to check if port $port is free" >&2
    exit 1
  fi
}

if port_in_use "$PORT"; then
  echo "Error: port $PORT is already in use" >&2
  exit 1
fi

# Export so the app's startup message can report the real port.
export ADMIN_PANEL_PORT="$PORT"
exec uv run uvicorn admin_panel.main:app --host 0.0.0.0 --port "$PORT"
