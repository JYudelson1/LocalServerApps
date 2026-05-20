# automation/ — control plane for sites & automations

One place that decides what runs on this server. State is split across two
files; `ctl.py` merges them and reconciles the actually-running services to
match, using the right OS backend.

```
services.json (tracked) ┐
                        ├─> ctl.py ─> backend (launchd on macOS | systemd on Linux)
runtime.json (per-host) ┘     ▲                          │
                              └──── admin_panel writes ───┘ (via ctl.py)
```

## Two state files

**`services.json` — the CATALOG (tracked by git).**
Defines what *can* run, shared to every server. No on/off state lives here.

| field | meaning |
|---|---|
| `kind` | `daemon` (long-running, has `port`, kept alive) or `periodic` (runs every `interval_sec`) |
| `dir` | working dir, relative to the `LocalServerApps/` root |
| `command` | shell command; `{port}` is substituted from the live port |
| `port` | default port for a daemon |
| `interval_sec` | for periodic jobs |
| `description` | shown in the admin panel |

**`runtime.json` — per-server STATE (gitignored).**
What's on/off *on this box*, and the live port each daemon is using. Backed up
locally, never propagated between servers. Auto-created if missing; on a fresh
server every service starts **disabled** until you turn it on.

```json
{ "services": { "shab-train-clock": { "enabled": true, "port": 8000 } } }
```

`ctl.py` overlays runtime onto catalog: `enabled` comes from runtime, `port`
from runtime if set else the catalog default. Toggling writes **only**
`runtime.json` — the shared catalog is never touched at runtime. (JSON, not
YAML, so programmatic writes don't mangle comments.)

## ctl.py

Stdlib-only, so any `python3` runs it.

```bash
./ctl.py list                 # desired + live status of everything
./ctl.py list --json          # same, machine-readable (the admin panel uses this)
./ctl.py enable <name>        # turn on  + apply
./ctl.py disable <name>       # turn off + apply
./ctl.py set-port <name> <p>  # change a daemon's port (refuses unless disabled)
./ctl.py apply                # reconcile everything to match runtime.json
./ctl.py setup                # one-time host setup (see Pi note below)
```

Daemon `command`s run *through* the site's `start.sh` (e.g.
`./start.sh {port}`), which guards against a manual double-run and a
port-already-in-use — so that protection applies whether a service is launched
by the backend or by hand. See [`../sites/CLAUDE.md`](../sites/CLAUDE.md).

## Backends

Picked automatically by OS (`backends/__init__.py`).

**macOS — launchd** (`~/Library/LaunchAgents/com.localserverapps.<name>.plist`)
Runs as you, no sudo. Survives ssh-out; stays up while the Mac is on and
logged in. `daemon` → `KeepAlive`; `periodic` → `StartInterval`.

**Linux/Pi — systemd user units** (`~/.config/systemd/user/lsa-<name>.{service,timer}`)
Runs as you, no root. `daemon` → `Restart=always`; `periodic` → `.service` +
`.timer`. Inherits secrets from the shared `../.env` via `EnvironmentFile`.

> **Pi persistence (important):** user services stop at logout unless lingering
> is on. Run **once** on the Pi:
> ```bash
> ./ctl.py setup        # == loginctl enable-linger $USER
> ```
> After that, enabled services start at boot and survive logout/reboot.

> The systemd backend is written to spec but has only been exercised on macOS
> so far. **When bringing up a Pi, follow [`PI_SETUP.md`](PI_SETUP.md)** — it
> walks through linger, the `XDG_RUNTIME_DIR`/SSH gotcha, the reboot test, and
> the bits that still need real-hardware validation.

## Logs

Service stdout/stderr → `../data/logs/<name>.{out,err}.log` (gitignored).
