"""macOS launchd backend (LaunchAgent scope: ~/Library/LaunchAgents).

Runs as the logged-in user, no sudo. Survives ssh-out and stays up as long
as the Mac is powered + logged in. Used on the Mac; the Pi uses systemd.
"""

from __future__ import annotations

import plistlib
import subprocess
from pathlib import Path

from .base import NOT_INSTALLED, RUNNING, STOPPED, UNKNOWN, Backend, Unit

LABEL_PREFIX = "com.localserverapps"
# Homebrew (Apple silicon + Intel) first so `uv`, `python3` etc. resolve.
PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"


def _label(name: str) -> str:
    return f"{LABEL_PREFIX}.{name}"


class LaunchdBackend(Backend):
    name = "launchd"

    def __init__(self) -> None:
        self._agents_dir = Path.home() / "Library" / "LaunchAgents"

    def _plist_path(self, name: str) -> Path:
        return self._agents_dir / f"{_label(name)}.plist"

    def install(self, unit: Unit) -> None:
        self._agents_dir.mkdir(parents=True, exist_ok=True)
        if unit.out_log:
            unit.out_log.parent.mkdir(parents=True, exist_ok=True)

        plist: dict = {
            "Label": _label(unit.name),
            "ProgramArguments": [
                "/bin/bash", "-lc",
                f"cd {unit.workdir} && exec {unit.command}",
            ],
            "EnvironmentVariables": {"PATH": PATH},
            "RunAtLoad": True,
        }
        if unit.kind == "periodic":
            plist["StartInterval"] = unit.interval_sec
            plist["KeepAlive"] = False
        else:  # daemon
            plist["KeepAlive"] = True
        if unit.out_log:
            plist["StandardOutPath"] = str(unit.out_log)
        if unit.err_log:
            plist["StandardErrorPath"] = str(unit.err_log)

        path = self._plist_path(unit.name)
        with open(path, "wb") as f:
            plistlib.dump(plist, f)

        # Reload cleanly: unload if present, then load.
        subprocess.run(["launchctl", "unload", str(path)],
                       capture_output=True)
        subprocess.run(["launchctl", "load", str(path)], check=True,
                       capture_output=True)

    def uninstall(self, unit_name: str) -> None:
        path = self._plist_path(unit_name)
        if path.exists():
            subprocess.run(["launchctl", "unload", str(path)],
                           capture_output=True)
            path.unlink()

    def status(self, unit_name: str) -> str:
        if not self._plist_path(unit_name).exists():
            return NOT_INSTALLED
        # `launchctl list <label>` exits 0 and prints a dict if loaded.
        res = subprocess.run(["launchctl", "list", _label(unit_name)],
                             capture_output=True, text=True)
        if res.returncode != 0:
            return STOPPED
        # "PID" key present => currently running; absent => loaded but idle
        # (normal for a periodic job between runs).
        for line in res.stdout.splitlines():
            if '"PID"' in line:
                return RUNNING
        return STOPPED if '"LastExitStatus"' in res.stdout else UNKNOWN
