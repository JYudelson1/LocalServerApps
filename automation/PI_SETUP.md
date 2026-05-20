# Bringing up a Raspberry Pi

The systemd backend (`backends/systemd.py`) is written to spec but has **only
run on the Mac's launchd path so far** — this checklist is how to validate it on
a real Pi. Work top to bottom; the ⚠️ items are the ones most likely to need a
fix.

## 0. Prereqs
- Raspberry Pi OS (Debian-based) with a normal user account (e.g. `pi`).
- The box is on the network and you can SSH in.
- Python 3.11+ available for the *sites* (uv installs its own if needed, so the
  system python only needs to run `ctl.py`, which is stdlib-only).

## 1. Get the code + secrets
```bash
git clone --recurse-submodules <repo-url> ~/LocalServerApps
cd ~/LocalServerApps
cp .env.example .env && nano .env      # fill in MTA key, PSFC creds, etc.
```

## 2. Bootstrap
```bash
./download.sh
```
This installs git + uv if missing, pulls latest, then brings services up via
`ctl.py`. ⚠️ Watch the output for:
- **uv install location** — the installer drops `uv` in `~/.local/bin` (or
  `~/.cargo/bin`). Confirm `command -v uv` works in a fresh shell; if not, that
  dir isn't on PATH. The unit files hardcode both via `%h/.local/bin:%h/.cargo/bin`
  — if uv lives elsewhere, edit `PATH` in `backends/systemd.py`.

## 3. Enable linger (persistence across reboot) ⚠️ most important
```bash
./automation/ctl.py setup
```
Expected: `Lingering enabled for '<user>' — services persist across logout/reboot.`
If it prints the **sudo hint** instead, run it and re-check:
```bash
sudo loginctl enable-linger $USER
loginctl show-user $USER --property=Linger   # must say Linger=yes
```
Without this, user services stop at logout and do NOT start at boot.

## 4. Verify services are up
```bash
./automation/ctl.py list                       # daemons should be "running"
systemctl --user list-units 'lsa-*'            # the actual units
journalctl --user -u lsa-shab-train-clock -n 50 --no-pager
```
⚠️ If `systemctl --user` errors with **"Failed to connect to bus"**, your SSH
session has no `XDG_RUNTIME_DIR`. `ctl.py` sets it automatically, but for manual
`systemctl --user` calls:
```bash
export XDG_RUNTIME_DIR=/run/user/$(id -u)
```

## 5. The real test: reboot ⚠️
```bash
sudo reboot
```
Wait for it to come back, then **without logging into a desktop session**, SSH
in and:
```bash
cd ~/LocalServerApps && ./automation/ctl.py list
```
Daemons should already be `running`. If they're not, linger (step 3) didn't
take. Also hit the admin panel from another device: `http://<pi-ip>:8900`.

## 6. Per-service gotchas
- **psfc-monitor (Playwright/Chromium on ARM):** needs `playwright install
  chromium` plus system libs, and ARM support is finicky. Verify the monitor
  runs by hand first: `cd scripts/psfc && ./run_monitor.sh` and read
  `monitor.log`.
- **Ordering vs network:** units use `After=network-online.target`, which is
  only meaningful if `NetworkManager-wait-online` (or `systemd-networkd-wait-online`)
  is enabled. Harmless if not, but if a service races the network on boot,
  enable that.

## 7. Day-to-day
- Toggle services from the admin panel, or `ctl.py enable/disable <name>`.
- Per-server on/off + ports live in `runtime.json` (gitignored). The Pi keeps
  its own — independent from the Mac.
- Logs: `data/logs/<name>.{out,err}.log` and `journalctl --user -u lsa-<name>`.

## Known-unvalidated (fix here if they bite)
- `%h` expansion inside `Environment=PATH=` in the unit file.
- `EnvironmentFile=` parsing of `.env` (systemd is stricter than bash `source`;
  fine for simple `KEY=value`, but quotes/special chars differ). Note the apps
  also load `.env` themselves, so this is mostly belt-and-suspenders.
- `bash -lc` sourcing the right profile for PATH under the user manager.
