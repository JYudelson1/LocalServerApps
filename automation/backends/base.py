"""Backend interface + the Unit value object both backends operate on.

A Backend knows how to install / uninstall / inspect ONE service on a given
OS (launchd on macOS, systemd on Linux). ctl.py picks the backend by OS and
hands it Unit objects built from the merged catalog + runtime state.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Unit:
    name: str               # e.g. "shab-train-clock"
    kind: str               # "daemon" (long-running) | "periodic" (every interval_sec)
    workdir: Path           # absolute working directory
    command: str            # shell command to run (port already substituted)
    description: str = ""
    interval_sec: int = 900  # only meaningful for kind == "periodic"
    out_log: Path | None = None
    err_log: Path | None = None


# Live status values backends report.
RUNNING = "running"
STOPPED = "stopped"
NOT_INSTALLED = "not-installed"
UNKNOWN = "unknown"


class Backend:
    """Abstract control backend. Subclasses implement per-OS mechanics."""

    name = "base"

    def install(self, unit: Unit) -> None:
        """Write the unit definition and start/enable it so it persists."""
        raise NotImplementedError

    def uninstall(self, unit_name: str) -> None:
        """Stop, disable, and remove the unit definition. Idempotent."""
        raise NotImplementedError

    def status(self, unit_name: str) -> str:
        """One of RUNNING / STOPPED / NOT_INSTALLED / UNKNOWN."""
        raise NotImplementedError
