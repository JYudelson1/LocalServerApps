# Adding a new site

Sites under `sites/` are long-running web daemons managed by the automation
layer (`../automation/`). Follow this checklist so a new site plugs into the
control plane, the admin panel, and the double-run guards automatically.

(Periodic jobs — things that run on an interval rather than staying up — go in
`../scripts/` instead, with a `run_*.sh`; register them with `"kind":
"periodic"` and an `interval_sec`.)

## Checklist

1. **Scaffold the app.** `sites/<name>/` with a `pyproject.toml` (use `uv`).
   Bind the server to `0.0.0.0` and accept a `--port` so the port is
   controllable from config, not hardcoded. Match ShabTrainClock's shape.

2. **Write `sites/<name>/start.sh`** — copy
   [`ShabTrainClock/start.sh`](ShabTrainClock/start.sh) or
   [`admin_panel/start.sh`](admin_panel/start.sh) and change two things:
   - the **`pgrep -f '<pattern>'`** pattern to something that uniquely matches
     *this* site's process (e.g. its module path), so the guard doesn't
     false-match another site;
   - the final **`exec …`** line to launch this server on `"$PORT"`.

   Keep the rest: the `PORT="${1:-<default>}"` arg, the already-running
   `pgrep` guard, and the `port_in_use` check (it falls back across
   `ss`/`lsof`/`fuser` so it works on both the Mac and the Pi). Then
   `chmod +x start.sh`.

   > Why start.sh and not the raw command: the catalog runs sites *through*
   > start.sh, so the no-double-run + port-free guards apply whether launched
   > by the automation backend or by hand.

3. **Register in the catalog** — add an entry to
   [`../automation/services.json`](../automation/services.json):
   ```json
   "<name>": {
     "kind": "daemon",
     "dir": "sites/<name>",
     "command": "./start.sh {port}",
     "port": <default-port>,
     "description": "<one line>"
   }
   ```
   `{port}` is filled from the live port. **Do NOT put `enabled` or a runtime
   port here** — the catalog is tracked/shared across servers; on/off and the
   live port are per-server and live in `runtime.json` (gitignored).

4. **Turn it on for this server** — toggle it in the admin panel, or:
   ```bash
   ../automation/ctl.py enable <name>
   ```
   That writes `runtime.json` and loads it via launchd (Mac) / systemd (Pi).

5. **Secrets** (if any) — add the keys to the shared `../../.env` and
   `../../.env.example`. Load them with
   `load_dotenv(find_dotenv(usecwd=True))` so the nested `.env` is found.
   Never put secrets in `config.yaml` or the catalog.

6. **Submodule?** Existing sites are git submodules (their own repos). If this
   site is a standalone repo, add it with `../add_submodule.sh`. If it only
   ever runs here (like `admin_panel`), a plain folder is fine.

7. **Verify** — `../automation/ctl.py list` shows it; load it and hit
   `http://<server-ip>:<port>`.

## Conventions

- Default to FastAPI + a static `index.html` (the established pattern here).
- Server-authoritative: poll/cache upstream APIs server-side; don't make the
  browser hit third-party APIs or hold keys.
- Add a `--port` flag and an env-var fallback; the automation layer owns the
  actual port via `runtime.json`.
