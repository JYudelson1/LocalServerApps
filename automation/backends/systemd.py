"""Linux systemd backend (user scope: ~/.config/systemd/user).

Runs as the logged-in user, no root. For persistence across reboot/logout on
a headless Pi you must enable lingering ONCE:

    loginctl enable-linger $USER

(ctl.py's `setup` command does this for you.) With linger on, user services
start at boot and survive logout — the systemd equivalent of a macOS
LaunchDaemon but without root papercuts.

  - daemon  -> <name>.service (Restart=always)
  - periodic-> <name>.service (oneshot) + <name>.timer (OnUnitActiveSec)

NOTE: written to spec but only exercised on the Pi — verify there.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .base import NOT_INSTALLED, RUNNING, STOPPED, UNKNOWN, Backend, Unit

UNIT_PREFIX = "lsa"  # systemd unit names: lsa-<name>.service / .timer
# Common locations for uv / pipx / user installs on a Pi, plus system bins.
PATH = "%h/.local/bin:%h/.cargo/bin:/usr/local/bin:/usr/bin:/bin"


def _svc(name: str) -> str:
    return f"{UNIT_PREFIX}-{name}.service"


def _timer(name: str) -> str:
    return f"{UNIT_PREFIX}-{name}.timer"


class SystemdBackend(Backend):
    name = "systemd"

    def __init__(self) -> None:
        self._unit_dir = Path.home() / ".config" / "systemd" / "user"
        # Path to the shared .env so units inherit secrets (MTA key, etc.).
        self._env_file = Path(__file__).resolve().parents[2] / ".env"

    def _uctl(self, *args: str, check: bool = False) -> subprocess.CompletedProcess:
        return subprocess.run(["systemctl", "--user", *args],
                              capture_output=True, text=True, check=check)

    def install(self, unit: Unit) -> None:
        self._unit_dir.mkdir(parents=True, exist_ok=True)
        if unit.out_log:
            unit.out_log.parent.mkdir(parents=True, exist_ok=True)

        env_line = (f"EnvironmentFile=-{self._env_file}\n"
                    if self._env_file.exists() else "")

        service = (
            "[Unit]\n"
            f"Description={unit.description or unit.name}\n"
            "After=network-online.target\n\n"
            "[Service]\n"
            f"WorkingDirectory={unit.workdir}\n"
            f"Environment=PATH={PATH}\n"
            f"{env_line}"
            f"ExecStart=/bin/bash -lc 'exec {unit.command}'\n"
        )
        if unit.kind == "periodic":
            service += "Type=oneshot\n\n[Install]\nWantedBy=default.target\n"
            timer = (
                "[Unit]\n"
                f"Description=Timer for {unit.name}\n\n"
                "[Timer]\n"
                f"OnBootSec={min(unit.interval_sec, 120)}\n"
                f"OnUnitActiveSec={unit.interval_sec}\n"
                "Persistent=true\n\n"
                "[Install]\nWantedBy=timers.target\n"
            )
            (self._unit_dir / _svc(unit.name)).write_text(service)
            (self._unit_dir / _timer(unit.name)).write_text(timer)
            self._uctl("daemon-reload")
            self._uctl("enable", "--now", _timer(unit.name), check=True)
        else:  # daemon
            service += ("Restart=always\nRestartSec=3\n\n"
                        "[Install]\nWantedBy=default.target\n")
            (self._unit_dir / _svc(unit.name)).write_text(service)
            self._uctl("daemon-reload")
            self._uctl("enable", "--now", _svc(unit.name), check=True)

    def uninstall(self, unit_name: str) -> None:
        for unit_file in (_timer(unit_name), _svc(unit_name)):
            path = self._unit_dir / unit_file
            if path.exists():
                self._uctl("disable", "--now", unit_file)
                path.unlink()
        self._uctl("daemon-reload")

    def status(self, unit_name: str) -> str:
        svc, timer = _svc(unit_name), _timer(unit_name)
        if not (self._unit_dir / svc).exists():
            return NOT_INSTALLED
        # For a periodic job the service is oneshot (inactive between runs);
        # the timer being active is what "on" means.
        target = timer if (self._unit_dir / timer).exists() else svc
        res = self._uctl("is-active", target)
        out = res.stdout.strip()
        if out == "active":
            return RUNNING
        if out in ("inactive", "failed"):
            return STOPPED
        return UNKNOWN

    def enable_linger(self) -> None:
        """Persist user services across logout/reboot. Needs polkit/sudo."""
        subprocess.run(["loginctl", "enable-linger", os.environ.get("USER", "")],
                       capture_output=True)
