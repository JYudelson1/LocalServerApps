#!/usr/bin/env python3
"""ctl.py — the single control plane for LocalServerApps sites + automations.

Two state files:
  - services.json  (CATALOG)  tracked by git, shared to every server: what CAN
                              run + defaults (kind, dir, command, default port).
  - runtime.json   (RUNTIME)  untracked, per-server: what's on/off here and the
                              live port each daemon uses. Auto-created if absent.

ctl.py merges them and reconciles the actually-running services to match, using
the launchd backend on macOS or systemd on Linux. The admin_panel site shells
out to this script so there's exactly one place that mutates state.

Stdlib-only on purpose, so any python3 (or the admin panel's venv) can run it.

Usage:
    ./ctl.py list [--json]          show desired + live status of every service
    ./ctl.py enable <name>          turn a service on (and apply)
    ./ctl.py disable <name>         turn a service off (and apply)
    ./ctl.py set-port <name> <port> change a daemon's port (must be disabled)
    ./ctl.py apply                  reconcile everything to match runtime.json
    ./ctl.py setup                  one-time host setup (linger on Linux)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backends import pick_backend  # noqa: E402
from backends.base import Unit  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                      # LocalServerApps/
CATALOG_PATH = HERE / "services.json"   # tracked, shared
RUNTIME_PATH = HERE / "runtime.json"    # untracked, per-server
LOG_DIR = ROOT / "data" / "logs"


def load_catalog() -> dict:
    with open(CATALOG_PATH) as f:
        return json.load(f)


def load_runtime() -> dict:
    """Per-server on/off + port state. Auto-create (all disabled) if missing."""
    if RUNTIME_PATH.exists():
        with open(RUNTIME_PATH) as f:
            return json.load(f)
    runtime = {
        "_comment": "Per-server runtime state. Gitignored. Auto-created.",
        "services": {},
    }
    save_runtime(runtime)
    return runtime


def save_runtime(runtime: dict) -> None:
    with open(RUNTIME_PATH, "w") as f:
        json.dump(runtime, f, indent=2)
        f.write("\n")


def merged(name: str, catalog: dict, runtime: dict) -> dict:
    """Catalog definition overlaid with this server's runtime on/off + port."""
    defn = catalog["services"][name]
    rt = runtime.get("services", {}).get(name, {})
    return {
        **defn,
        "enabled": bool(rt.get("enabled", False)),
        # Live port if the runtime recorded one, else the catalog default.
        "port": rt.get("port", defn.get("port")),
    }


def make_unit(name: str, svc: dict) -> Unit:
    command = svc["command"].format(port=svc.get("port", ""))
    return Unit(
        name=name,
        kind=svc.get("kind", "daemon"),
        workdir=(ROOT / svc["dir"]).resolve(),
        command=command,
        description=svc.get("description", ""),
        interval_sec=int(svc.get("interval_sec", 900)),
        out_log=LOG_DIR / f"{name}.out.log",
        err_log=LOG_DIR / f"{name}.err.log",
    )


def reconcile_one(backend, name: str, svc: dict) -> None:
    """Make reality match svc['enabled'] for one service."""
    if svc.get("enabled"):
        backend.install(make_unit(name, svc))
    else:
        backend.uninstall(name)


def cmd_apply(catalog: dict, runtime: dict, backend) -> None:
    for name in catalog["services"]:
        svc = merged(name, catalog, runtime)
        reconcile_one(backend, name, svc)
        print(f"  {'on ' if svc['enabled'] else 'off'}  {name}")


def cmd_set_enabled(catalog: dict, runtime: dict, backend,
                    name: str, enabled: bool) -> None:
    if name not in catalog["services"]:
        sys.exit(f"Unknown service: {name}")
    rt = runtime.setdefault("services", {}).setdefault(name, {})
    rt["enabled"] = enabled
    # On enable, pin the live port for a daemon (default from catalog if unset)
    # so the runtime always reflects what port it's actually on.
    defn = catalog["services"][name]
    if enabled and defn.get("kind", "daemon") == "daemon" and "port" not in rt:
        rt["port"] = defn.get("port")
    save_runtime(runtime)
    reconcile_one(backend, name, merged(name, catalog, runtime))
    print(f"{name} -> {'enabled' if enabled else 'disabled'}")


def cmd_set_port(catalog: dict, runtime: dict, name: str, port: int) -> None:
    if name not in catalog["services"]:
        sys.exit(f"Unknown service: {name}")
    defn = catalog["services"][name]
    if defn.get("kind", "daemon") != "daemon":
        sys.exit(f"{name} is not a daemon; it has no port.")
    rt = runtime.setdefault("services", {}).setdefault(name, {})
    if rt.get("enabled"):
        sys.exit(f"Refusing to change port while {name} is enabled. "
                 f"Disable it first.")
    rt["port"] = port
    save_runtime(runtime)
    print(f"{name} port -> {port}")


def cmd_list(catalog: dict, runtime: dict, backend, as_json: bool) -> None:
    rows = []
    for name in catalog["services"]:
        svc = merged(name, catalog, runtime)
        rows.append({
            "name": name,
            "kind": svc.get("kind", "daemon"),
            "enabled": svc["enabled"],
            "live": backend.status(name),
            "port": svc.get("port"),
            "interval_sec": svc.get("interval_sec"),
            "description": svc.get("description", ""),
        })
    if as_json:
        print(json.dumps(rows, indent=2))
        return
    print(f"{'SERVICE':<22} {'KIND':<9} {'DESIRED':<8} {'LIVE'}")
    for r in rows:
        desired = "on" if r["enabled"] else "off"
        print(f"{r['name']:<22} {r['kind']:<9} {desired:<8} {r['live']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="LocalServerApps control plane")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list").add_argument("--json", action="store_true")
    sub.add_parser("apply")
    sub.add_parser("setup")
    p_en = sub.add_parser("enable"); p_en.add_argument("name")
    p_dis = sub.add_parser("disable"); p_dis.add_argument("name")
    p_port = sub.add_parser("set-port")
    p_port.add_argument("name"); p_port.add_argument("port", type=int)
    args = parser.parse_args()

    catalog = load_catalog()
    runtime = load_runtime()
    backend = pick_backend()

    if args.cmd == "list":
        cmd_list(catalog, runtime, backend, args.json)
    elif args.cmd == "apply":
        cmd_apply(catalog, runtime, backend)
    elif args.cmd == "enable":
        cmd_set_enabled(catalog, runtime, backend, args.name, True)
    elif args.cmd == "disable":
        cmd_set_enabled(catalog, runtime, backend, args.name, False)
    elif args.cmd == "set-port":
        cmd_set_port(catalog, runtime, args.name, args.port)
    elif args.cmd == "setup":
        if hasattr(backend, "enable_linger"):
            backend.enable_linger()  # prints its own confirmation / sudo hint
        else:
            print("Nothing to set up for this backend (launchd needs no linger).")


if __name__ == "__main__":
    main()
