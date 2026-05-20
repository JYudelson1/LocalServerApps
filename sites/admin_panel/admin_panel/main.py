"""Admin panel: list sites/automations, toggle them, show server load.

All state mutations go through automation/ctl.py (the single control plane) so
this app holds no control logic of its own — it just renders + relays.

LAN-only by design: this can start/stop server processes, so don't expose it
to the internet. Reach it from any device on your wifi.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

import psutil
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# sites/admin_panel/admin_panel/main.py -> LocalServerApps/ is parents[3]
ROOT = Path(__file__).resolve().parents[3]
CTL = ROOT / "automation" / "ctl.py"
STATIC_DIR = Path(__file__).resolve().parents[1] / "static"


def lan_ip() -> str:
    """Best-effort primary LAN IP (no traffic actually sent)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # start.sh / main() export ADMIN_PANEL_PORT so we can report the real port.
    port = os.environ.get("ADMIN_PANEL_PORT", "8900")
    ip = lan_ip()
    print(f"\n  ── Admin panel ready → http://{ip}:{port}  "
          f"(or http://localhost:{port})\n", flush=True)
    yield


app = FastAPI(lifespan=lifespan)


def run_ctl(*args: str) -> str:
    """Invoke the control plane. ctl.py is stdlib-only, so our venv runs it."""
    proc = subprocess.run(
        [sys.executable, str(CTL), *args],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=f"ctl.py {' '.join(args)} failed: {proc.stderr.strip()}",
        )
    return proc.stdout


class ToggleBody(BaseModel):
    enabled: bool


class PortBody(BaseModel):
    port: int


@app.get("/api/state")
async def get_state() -> JSONResponse:
    services = json.loads(run_ctl("list", "--json"))
    return JSONResponse({"services": services})


@app.post("/api/services/{name}/toggle")
async def toggle_service(name: str, body: ToggleBody) -> JSONResponse:
    run_ctl("enable" if body.enabled else "disable", name)
    return JSONResponse({"ok": True, "name": name, "enabled": body.enabled})


@app.post("/api/services/{name}/port")
async def set_port(name: str, body: PortBody) -> JSONResponse:
    # ctl.py refuses if the service is currently enabled (must disable first).
    run_ctl("set-port", name, str(body.port))
    return JSONResponse({"ok": True, "name": name, "port": body.port})


@app.get("/api/system")
async def get_system() -> JSONResponse:
    vm = psutil.virtual_memory()
    return JSONResponse({
        "mem_total": vm.total,
        "mem_used": vm.used,
        "mem_percent": vm.percent,
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "load_avg": list(psutil.getloadavg()),
        "uptime_sec": int(time.time() - psutil.boot_time()),
    })


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def root():
    return FileResponse(STATIC_DIR / "index.html",
                        headers={"Cache-Control": "no-store"})


def main() -> None:
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="Admin panel server")
    parser.add_argument("--port", type=int,
                        default=int(os.environ.get("ADMIN_PANEL_PORT", "8900")))
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()
    # So the startup-message lifespan reports the actual port.
    os.environ["ADMIN_PANEL_PORT"] = str(args.port)
    uvicorn.run("admin_panel.main:app", host=args.host, port=args.port,
                reload=False)


if __name__ == "__main__":
    main()
