#!/usr/bin/env python3
"""
Radxa Cubie A7A - Dashboard Server
====================================
FastAPI backend serving the web-based command center.
Provides WebSocket endpoints for terminal, IMU streaming, and debug
logging, plus REST endpoints for file browsing, GPIO status, and
system information.
"""

import asyncio
import fcntl
import json
import logging
import os
import pty
import select
import signal
import struct
import subprocess
import sys
import termios
import time
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

# --------------- Optional hardware imports --------------- #
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from ism6hg256x import ISM6HG256X, I2C_ADDR_SA0_LOW
    IMU_AVAILABLE = True
except Exception:
    IMU_AVAILABLE = False

# --------------- IMU singleton --------------- #
_imu_instance = None
_imu_lock = asyncio.Lock() if hasattr(asyncio, 'Lock') else None

def _imu_init():
    global _imu_instance
    if _imu_instance is not None:
        return True, "Already initialised"
    if not IMU_AVAILABLE:
        return False, "ISM6HG256X driver module not found on this host"
    try:
        _imu_instance = ISM6HG256X(bus_number=7, address=I2C_ADDR_SA0_LOW)
        logger.info("IMU initialised on /dev/i2c-7 at 0x6A")
        return True, "Sensor active"
    except Exception as e:
        logger.error("IMU init failed: %s", e)
        return False, str(e)

def _imu_deinit():
    global _imu_instance
    if _imu_instance is None:
        return True, "Already idle"
    try:
        _imu_instance.close()
    except Exception:
        pass
    _imu_instance = None
    logger.info("IMU deinitialised")
    return True, "Sensor powered down"

# --------------- Logging setup --------------- #
log_buffer: list[dict] = []

class BufferLogHandler(logging.Handler):
    def emit(self, record):
        entry = {
            "time": time.strftime("%H:%M:%S", time.localtime(record.created)),
            "level": record.levelname,
            "msg": self.format(record),
        }
        log_buffer.append(entry)
        if len(log_buffer) > 1000:
            del log_buffer[:200]

buf_handler = BufferLogHandler()
buf_handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
logging.root.addHandler(buf_handler)
logging.root.setLevel(logging.INFO)
logger = logging.getLogger("dashboard")

# --------------- FastAPI app --------------- #
app = FastAPI(title="Radxa Cubie A7A Dashboard")
STATIC = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


# ===================== REST ENDPOINTS ===================== #

@app.get("/")
async def index():
    return FileResponse(str(STATIC / "index.html"))


@app.get("/api/sysinfo")
async def sysinfo():
    info = {"hostname": os.uname().nodename, "imu": IMU_AVAILABLE}
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            info["cpu_temp"] = round(int(f.read().strip()) / 1000.0, 1)
    except Exception:
        info["cpu_temp"] = None
    try:
        with open("/proc/meminfo") as f:
            m = {}
            for ln in f:
                p = ln.split()
                if p[0] in ("MemTotal:", "MemAvailable:", "MemFree:"):
                    m[p[0].rstrip(":")] = int(p[1])
            info["mem_total"] = m.get("MemTotal", 0) // 1024
            info["mem_avail"] = m.get("MemAvailable", m.get("MemFree", 0)) // 1024
    except Exception:
        info["mem_total"] = info["mem_avail"] = 0
    try:
        with open("/proc/uptime") as f:
            info["uptime"] = int(float(f.read().split()[0]))
    except Exception:
        info["uptime"] = 0
    try:
        info["load"] = [round(x, 2) for x in os.getloadavg()]
    except Exception:
        info["load"] = [0, 0, 0]
    return info


@app.get("/api/files")
async def list_files(path: str = "/home/radxa"):
    p = os.path.abspath(path)
    entries = []
    try:
        for e in sorted(os.scandir(p), key=lambda x: (not x.is_dir(), x.name.lower())):
            try:
                st = e.stat(follow_symlinks=False)
                entries.append({
                    "name": e.name, "path": e.path,
                    "dir": e.is_dir(follow_symlinks=False),
                    "size": st.st_size if not e.is_dir() else None,
                    "mtime": st.st_mtime,
                })
            except PermissionError:
                entries.append({"name": e.name, "path": e.path, "dir": False, "error": True})
    except PermissionError:
        return JSONResponse({"error": "Permission denied"}, 403)
    except FileNotFoundError:
        return JSONResponse({"error": "Not found"}, 404)
    return {"path": p, "parent": str(Path(p).parent), "entries": entries}


@app.get("/api/file-content")
async def file_content(path: str):
    p = os.path.abspath(path)
    try:
        sz = os.path.getsize(p)
        if sz > 512 * 1024:
            return JSONResponse({"error": "File too large"}, 413)
        with open(p, "r", errors="replace") as f:
            return {"path": p, "content": f.read(), "size": sz}
    except (PermissionError, FileNotFoundError, IsADirectoryError) as e:
        return JSONResponse({"error": str(e)}, 400)


@app.get("/api/gpio")
async def gpio_status():
    pins = []
    gpio_base = "/sys/class/gpio"
    if not os.path.isdir(gpio_base):
        return {"pins": [], "error": "sysfs gpio not available"}
    for name in sorted(os.listdir(gpio_base)):
        if not name.startswith("gpio") or name == "gpiochip0" or "chip" in name:
            continue
        pin_path = os.path.join(gpio_base, name)
        if not os.path.isdir(pin_path):
            continue
        info = {"name": name}
        try:
            with open(os.path.join(pin_path, "direction")) as f:
                info["dir"] = f.read().strip()
            with open(os.path.join(pin_path, "value")) as f:
                info["val"] = int(f.read().strip())
        except Exception as e:
            info["error"] = str(e)
        pins.append(info)
    # Also try gpioinfo if available
    chip_info = []
    for name in sorted(os.listdir(gpio_base)):
        if "chip" in name:
            chip = {"name": name}
            try:
                with open(os.path.join(gpio_base, name, "label")) as f:
                    chip["label"] = f.read().strip()
                with open(os.path.join(gpio_base, name, "ngpio")) as f:
                    chip["ngpio"] = int(f.read().strip())
                with open(os.path.join(gpio_base, name, "base")) as f:
                    chip["base"] = int(f.read().strip())
            except Exception:
                pass
            chip_info.append(chip)
    return {"pins": pins, "chips": chip_info}


@app.get("/api/imu/status")
async def imu_status():
    return {
        "driver": IMU_AVAILABLE,
        "active": _imu_instance is not None,
        "address": "0x6A",
        "bus": 7,
    }


@app.post("/api/imu/init")
async def imu_init_endpoint():
    ok, msg = _imu_init()
    return {"ok": ok, "msg": msg}


@app.post("/api/imu/deinit")
async def imu_deinit_endpoint():
    ok, msg = _imu_deinit()
    return {"ok": ok, "msg": msg}


@app.post("/api/imu/reset")
async def imu_reset_endpoint():
    if _imu_instance:
        _imu_instance.reset_orientation()
        return {"ok": True, "msg": "Orientation reset"}
    return {"ok": False, "msg": "IMU not initialised"}


# ===================== WEBSOCKET ENDPOINTS ===================== #

@app.websocket("/ws/terminal")
async def ws_terminal(ws: WebSocket):
    await ws.accept()
    master_fd, slave_fd = pty.openpty()
    env = os.environ.copy()
    env.update({"TERM": "xterm-256color", "COLUMNS": "120", "ROWS": "30"})
    proc = subprocess.Popen(
        ["/bin/bash"], stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
        preexec_fn=os.setsid, env=env,
    )
    os.close(slave_fd)
    flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
    fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
    logger.info("Terminal session opened (pid %d)", proc.pid)

    async def reader():
        while True:
            await asyncio.sleep(0.015)
            try:
                data = os.read(master_fd, 8192)
                if data:
                    await ws.send_text(data.decode("utf-8", errors="replace"))
            except (OSError, BlockingIOError):
                pass
            except Exception:
                break

    task = asyncio.create_task(reader())
    try:
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            text = msg.get("text", "")
            if not text:
                continue
            if text.startswith("\x01RESIZE:"):
                try:
                    cols, rows = text.split(":", 1)[1].split(",")
                    fcntl.ioctl(master_fd, termios.TIOCSWINSZ,
                                struct.pack("HHHH", int(rows), int(cols), 0, 0))
                except Exception:
                    pass
            else:
                os.write(master_fd, text.encode("utf-8"))
    except WebSocketDisconnect:
        pass
    finally:
        task.cancel()
        os.close(master_fd)
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except Exception:
            pass
        logger.info("Terminal session closed")


@app.websocket("/ws/imu")
async def ws_imu(ws: WebSocket):
    await ws.accept()
    if _imu_instance is None:
        await ws.send_json({"error": "IMU not initialised. Use the Init button to start the sensor."})
        await ws.close()
        return
    imu = _imu_instance
    logger.info("IMU WebSocket stream started")
    try:
        while True:
            if _imu_instance is None:
                await ws.send_json({"error": "IMU was deinitialised"})
                break
            roll, pitch, yaw = imu.update_orientation()
            ax, ay, az = imu.read_accel()
            gx, gy, gz = imu.read_gyro()
            await ws.send_json({
                "r": round(roll, 2), "p": round(pitch, 2), "y": round(yaw, 2),
                "a": [round(ax, 3), round(ay, 3), round(az, 3)],
                "g": [round(gx, 2), round(gy, 2), round(gz, 2)],
            })
            await asyncio.sleep(0.02)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("IMU stream error: %s", e)
    finally:
        logger.info("IMU WebSocket stream closed")


@app.websocket("/ws/logs")
async def ws_logs(ws: WebSocket):
    await ws.accept()
    for entry in log_buffer[-100:]:
        await ws.send_json(entry)
    idx = len(log_buffer)
    try:
        while True:
            await asyncio.sleep(0.3)
            cur = len(log_buffer)
            if cur > idx:
                for entry in log_buffer[idx:cur]:
                    await ws.send_json(entry)
                idx = cur
    except WebSocketDisconnect:
        pass


# ===================== ENTRY POINT ===================== #

if __name__ == "__main__":
    logger.info("Dashboard server starting on 0.0.0.0:8080")
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
