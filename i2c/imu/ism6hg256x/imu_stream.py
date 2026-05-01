#!/usr/bin/env python3
"""
ISM6HG256X IMU - Headless Stream
=================================
Runs on the Radxa Cubie A7A without a display.  Reads the IMU over I2C
and prints CSV orientation data (roll, pitch, yaw) to stdout at the
configured sample rate.

This output can be piped to a file, consumed by a network socket, or
forwarded over SSH to a remote visualizer.

Usage
-----
  python3 imu_stream.py                     # default 100 Hz to stdout
  python3 imu_stream.py | tee log.csv       # log and display
  python3 imu_stream.py --rate 50           # 50 samples/sec
"""

import argparse
import sys
import time

from ism6hg256x import ISM6HG256X, I2C_ADDR_SA0_LOW


def main():
    parser = argparse.ArgumentParser(
        description="Stream ISM6HG256X orientation data over I2C."
    )
    parser.add_argument(
        "--bus", type=int, default=7,
        help="I2C bus number (default: 7)",
    )
    parser.add_argument(
        "--addr", type=lambda x: int(x, 0), default=I2C_ADDR_SA0_LOW,
        help="I2C address in hex (default: 0x6A)",
    )
    parser.add_argument(
        "--rate", type=int, default=100,
        help="Output rate in Hz (default: 100)",
    )
    args = parser.parse_args()

    interval = 1.0 / args.rate

    print(f"# ISM6HG256X stream  bus={args.bus}  addr=0x{args.addr:02X}  rate={args.rate} Hz",
          file=sys.stderr)

    try:
        imu = ISM6HG256X(bus_number=args.bus, address=args.addr)
    except Exception as e:
        print(f"Init failed: {e}", file=sys.stderr)
        sys.exit(1)

    # CSV header
    print("roll,pitch,yaw")

    try:
        while True:
            t0 = time.monotonic()
            roll, pitch, yaw = imu.update_orientation()
            print(f"{roll:.4f},{pitch:.4f},{yaw:.4f}", flush=True)
            elapsed = time.monotonic() - t0
            if elapsed < interval:
                time.sleep(interval - elapsed)
    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)
    finally:
        imu.close()


if __name__ == "__main__":
    main()
