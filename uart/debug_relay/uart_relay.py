#!/usr/bin/env python3
"""
UART Debug Relay (Radxa side)
=============================
Bidirectional debug log relay over UART.

Outbound (Radxa -> Remote):
    Tails the system journal and forwards each line over UART.

Inbound (Remote -> Radxa):
    Accepts commands from the remote end, executes them in a shell,
    and transmits the output back over UART with a response delimiter.

Wire protocol (text-based, newline-delimited):
    Outbound log lines are prefixed with "[LOG] "
    Inbound commands are plain text terminated by newline.
    Command responses are bracketed by "[RSP]" and "[/RSP]" lines.
"""

import os
import signal
import subprocess
import sys
import threading
import time
from periphery import Serial

# ------------------------------------------------------------------ #
#  Configuration
# ------------------------------------------------------------------ #
DEFAULT_PORT = "/dev/ttyS2"
DEFAULT_BAUD = 115200
LOG_CMD = ["journalctl", "-f", "--no-pager", "-o", "short-monotonic"]


def log_forwarder(ser: Serial, stop: threading.Event):
    """Tail system logs and send over UART."""
    proc = subprocess.Popen(
        LOG_CMD,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )
    try:
        while not stop.is_set():
            line = proc.stdout.readline()
            if not line:
                time.sleep(0.1)
                continue
            payload = f"[LOG] {line.rstrip()}\n"
            try:
                ser.write(payload.encode("utf-8", errors="replace"))
            except Exception as e:
                print(f"UART write error: {e}", file=sys.stderr)
    finally:
        proc.terminate()
        proc.wait()


def command_listener(ser: Serial, stop: threading.Event):
    """Read commands from UART, execute them, send output back."""
    buf = b""
    while not stop.is_set():
        try:
            data = ser.read(256, timeout_ms=200)
        except Exception:
            time.sleep(0.1)
            continue
        if not data:
            continue
        buf += data
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            cmd = line.decode("utf-8", errors="replace").strip()
            if not cmd:
                continue
            print(f"[RX CMD] {cmd}")
            try:
                result = subprocess.run(
                    cmd, shell=True, capture_output=True,
                    text=True, timeout=10,
                )
                output = result.stdout + result.stderr
            except subprocess.TimeoutExpired:
                output = "[timeout]\n"
            except Exception as e:
                output = f"[error: {e}]\n"
            response = f"[RSP]\n{output.rstrip()}\n[/RSP]\n"
            try:
                ser.write(response.encode("utf-8", errors="replace"))
            except Exception as e:
                print(f"UART write error: {e}", file=sys.stderr)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="UART Debug Relay")
    parser.add_argument("-p", "--port", default=DEFAULT_PORT,
                        help=f"UART device (default: {DEFAULT_PORT})")
    parser.add_argument("-b", "--baud", type=int, default=DEFAULT_BAUD,
                        help=f"Baud rate (default: {DEFAULT_BAUD})")
    args = parser.parse_args()

    print(f"UART Debug Relay starting on {args.port} @ {args.baud} baud")
    ser = Serial(args.port, args.baud)

    stop = threading.Event()

    def shutdown(*_):
        print("\nShutting down ...")
        stop.set()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    t_log = threading.Thread(target=log_forwarder, args=(ser, stop),
                             daemon=True, name="log-fwd")
    t_cmd = threading.Thread(target=command_listener, args=(ser, stop),
                             daemon=True, name="cmd-listen")
    t_log.start()
    t_cmd.start()

    print("Relay active.  Ctrl+C to stop.")
    stop.wait()
    time.sleep(0.3)
    ser.close()
    print("Done.")


if __name__ == "__main__":
    main()
