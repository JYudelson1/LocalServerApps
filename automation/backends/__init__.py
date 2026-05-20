"""Control backends. pick_backend() chooses by OS."""

from __future__ import annotations

import platform

from .base import Backend


def pick_backend() -> Backend:
    system = platform.system()
    if system == "Darwin":
        from .launchd import LaunchdBackend
        return LaunchdBackend()
    if system == "Linux":
        from .systemd import SystemdBackend
        return SystemdBackend()
    raise RuntimeError(f"No automation backend for platform: {system}")
