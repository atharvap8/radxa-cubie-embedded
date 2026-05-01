#!/usr/bin/env python3
"""
UART Debug Receiver (Remote / PC side)
======================================
Connects to a serial port (USB-to-UART adapter), displays incoming
log lines from the Radxa relay, and accepts keyboard input to send
commands back.

Usage:
    python3 uart_receiver.py -p /dev/ttyUSB0 -b 115200
"""

import sys
import signal
import threading
import time

try:
    import serial  # pyserial
except ImportError:
    print("pyserial is required on the receiver side:")
    print("  pip install pyserial")
    sys.exit(1)

DEFAULT_PORT = "/dev/ttyUSB0"
DEFAULT_BAUD = 115200


def reader(ser: serial.Serial, stop: threading.Event):
    """Read and display data from UART."""
    while not stop.is_set():
        try:
            line = ser.readline()
            if line:
                text = line.decode("utf-8", errors="replace").rstrip()
                if text.startswith("[RSP]"):
                    print("\033[33m--- response start ---\033[0m")
                elif text.startswith("[/RSP]"):
                    print("\033[33m--- response end ---\033[0m")
                elif text.startswith("[LOG]"):
                    print(f"\033[36m{text}\033[0m")
                else:
                    print(text)
        except serial.SerialException:
            break
        except Exception:
            time.sleep(0.05)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="UART Debug Receiver")
    parser.add_argument("-p", "--port", default=DEFAULT_PORT,
                        help=f"Serial port (default: {DEFAULT_PORT})")
    parser.add_argument("-b", "--baud", type=int, default=DEFAULT_BAUD,
                        help=f"Baud rate (default: {DEFAULT_BAUD})")
    args = parser.parse_args()

    print(f"Connecting to {args.port} @ {args.baud} baud ...")
    try:
        ser = serial.Serial(args.port, args.baud, timeout=0.5)
    except Exception as e:
        print(f"Failed: {e}")
        sys.exit(1)

    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())

    t = threading.Thread(target=reader, args=(ser, stop), daemon=True)
    t.start()

    print("Receiving logs.  Type a command and press Enter to send.")
    print("Press Ctrl+C to exit.\n")

    try:
        while not stop.is_set():
            try:
                cmd = input()
            except EOFError:
                break
            if stop.is_set():
                break
            ser.write((cmd + "\n").encode("utf-8"))
    except KeyboardInterrupt:
        pass

    stop.set()
    time.sleep(0.2)
    ser.close()
    print("\nDisconnected.")


if __name__ == "__main__":
    main()
