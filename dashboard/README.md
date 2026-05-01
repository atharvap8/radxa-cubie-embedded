# Radxa Cubie A7A Dashboard

Browser-based command centre for the Radxa Cubie A7A, served over
the local network on port 8080.

## Features

| Module    | Description                                       |
|-----------|---------------------------------------------------|
| Terminal  | Full interactive shell (xterm.js + WebSocket PTY) |
| Files     | Directory browser with navigation                 |
| GPIO      | Live GPIO pin state monitor                       |
| IMU       | ISM6HG256X 3D orientation visualiser with init /  |
|           | deinit / reset controls                           |
| rsetup    | Board configuration TUI launcher                  |
| Logger    | Live system log viewer                            |
| System    | CPU, memory, disk, and temperature overview       |

## Architecture

```
Browser (any device on LAN)
    │
    │  HTTP + WebSocket
    │
    ▼
FastAPI / Uvicorn  (server.py)
    │
    ├── Static files (index.html, style.css, app.js)
    ├── REST API (/api/imu/init, /api/system, /api/files, ...)
    ├── WebSocket /ws/terminal  (PTY shell)
    └── WebSocket /ws/imu       (sensor stream)
```

## Prerequisites

```bash
pip install fastapi 'uvicorn[standard]' python-periphery
```

## Usage

```bash
cd ~/embedded/dashboard
python3 server.py
```

The dashboard is accessible at `http://<radxa-ip>:8080`.

Alternatively, use the startup script:
```bash
./start_dashboard.sh
```

## IMU integration

The dashboard imports the ISM6HG256X driver from
`../i2c/imu/ism6hg256x/`.  The IMU must be initialised via the
dashboard UI (Init button) before orientation data streams.

## Dependencies

```
fastapi
uvicorn[standard]
python-periphery
```
