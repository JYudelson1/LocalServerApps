# admin_panel

Web UI to see/toggle every site + automation and watch server load. A thin
front-end over [`automation/ctl.py`](../../automation/README.md) — it holds no
control logic, just renders state and relays toggles to the control plane.

## Run

```bash
uv sync
uv run uvicorn admin_panel.main:app --host 0.0.0.0 --port 8900
# or, once it's enabled in runtime.json (it is, by default):
#   ../../automation/ctl.py apply
```

Visit `http://<server-ip>:8900` from any device on your wifi.

## What it shows

- **System**: memory %, CPU %, load average, uptime (via `psutil`).
- **Sites** (daemons) and **Automations** (periodic) with live status badges
  (`running` / `stopped` / `not-installed`) and an on/off toggle each.

## API

| route | does |
|---|---|
| `GET /api/state` | service list + live status (`ctl.py list --json`) |
| `POST /api/services/{name}/toggle` | body `{"enabled": bool}` → `ctl.py enable/disable` |
| `POST /api/services/{name}/port` | body `{"port": int}` → `ctl.py set-port` (refused unless the service is disabled) |
| `GET /api/system` | memory / cpu / load / uptime |

The port field in the UI is editable only while a daemon is **disabled**; you
then hit **save** to write it. (A running service can't have its port changed
out from under it.)

## Security

**LAN-only by design.** This can start/stop server processes, so there's no
auth and it should never be port-forwarded to the internet. To reach it from
outside your network, put it behind a tunnel (Tailscale / Cloudflare Tunnel)
rather than opening a port — and add an auth gate first.

## Note on toggling the panel itself

`admin-panel` is in the catalog and enabled in `runtime.json`, so it can manage
itself. If you toggle it **off** from the UI it'll stop — recover from a shell
with:

```bash
../../automation/ctl.py enable admin-panel
```
