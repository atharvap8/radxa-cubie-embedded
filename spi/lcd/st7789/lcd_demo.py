#!/usr/bin/env python3
"""
LCD Demo Application
====================
Demonstrates the ST7789 driver capabilities: colour fills,
geometric primitives, text rendering, and a live system status
display.
"""

import os
import time
import sys
from st7789 import (
    ST7789, BLACK, WHITE, RED, GREEN, BLUE, CYAN, MAGENTA,
    YELLOW, ORANGE, PURPLE, GRAY, DARK_GRAY, LIGHT_GRAY, color565,
)


def read_cpu_temp() -> str:
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return f"{int(f.read().strip()) / 1000:.1f} C"
    except Exception:
        return "N/A"


def read_mem() -> str:
    try:
        with open("/proc/meminfo") as f:
            info = {}
            for line in f:
                parts = line.split()
                if parts[0] in ("MemTotal:", "MemAvailable:"):
                    info[parts[0].rstrip(":")] = int(parts[1])
            total = info.get("MemTotal", 0) // 1024
            avail = info.get("MemAvailable", 0) // 1024
            return f"{total - avail}/{total} MB"
    except Exception:
        return "N/A"


def read_uptime() -> str:
    try:
        with open("/proc/uptime") as f:
            sec = int(float(f.read().split()[0]))
            h, m = divmod(sec // 60, 60)
            return f"{h}h {m}m"
    except Exception:
        return "N/A"


def read_hostname() -> str:
    return os.uname().nodename


def demo_colour_wash(lcd: ST7789):
    """Cycle through solid colour fills."""
    colours = [
        ("RED",     RED),
        ("GREEN",   GREEN),
        ("BLUE",    BLUE),
        ("CYAN",    CYAN),
        ("MAGENTA", MAGENTA),
        ("YELLOW",  YELLOW),
        ("WHITE",   WHITE),
    ]
    for name, c in colours:
        lcd.fill(c)
        fg = BLACK if c in (WHITE, YELLOW, CYAN) else WHITE
        lcd.text(name, 10, 10, fg, c, 3)
        time.sleep(0.6)


def demo_shapes(lcd: ST7789):
    """Draw assorted geometric primitives."""
    lcd.fill(BLACK)
    lcd.text("Shapes", 10, 4, WHITE, BLACK, 2)

    lcd.rect(10, 30, 60, 40, RED)
    lcd.fill_rect(80, 30, 60, 40, GREEN)
    lcd.rect(150, 30, 60, 40, BLUE)
    lcd.fill_rect(155, 35, 50, 30, BLUE)

    lcd.circle(50, 110, 25, YELLOW)
    lcd.circle(120, 110, 30, CYAN)
    lcd.circle(190, 110, 20, MAGENTA)

    lcd.line(10, 160, 230, 200, ORANGE)
    lcd.line(10, 200, 230, 160, PURPLE)
    lcd.hline(10, 220, 220, GRAY)

    lcd.text("lines, rects, circles", 10, 240, LIGHT_GRAY, BLACK, 1)
    time.sleep(2)


def demo_text_scales(lcd: ST7789):
    """Show text at multiple scales."""
    lcd.fill(BLACK)
    lcd.text("Scale 1", 10, 10, WHITE, BLACK, 1)
    lcd.text("Scale 2", 10, 30, CYAN, BLACK, 2)
    lcd.text("Scale 3", 10, 60, YELLOW, BLACK, 3)
    lcd.text("Scale 4", 10, 100, RED, BLACK, 4)
    lcd.text("0123456789", 10, 150, GREEN, BLACK, 2)
    lcd.text("!@#$%^&*()", 10, 180, ORANGE, BLACK, 2)
    time.sleep(2)


def demo_status_monitor(lcd: ST7789, duration: int = 15):
    """Live system status display, refreshing every second."""
    lcd.fill(BLACK)
    lcd.text("SYSTEM MONITOR", 10, 4, CYAN, BLACK, 2)
    lcd.hline(0, 24, lcd.width, DARK_GRAY)

    hostname = read_hostname()
    lcd.text(f"Host: {hostname}", 10, 32, WHITE, BLACK, 1)

    labels = [
        (50,  "CPU Temp:"),
        (66,  "Memory:"),
        (82,  "Uptime:"),
    ]
    for y, label in labels:
        lcd.text(label, 10, y, GRAY, BLACK, 1)

    for _ in range(duration):
        lcd.fill_rect(80, 50, 150, 8, BLACK)
        lcd.text(read_cpu_temp(), 80, 50, GREEN, BLACK, 1)
        lcd.fill_rect(80, 66, 150, 8, BLACK)
        lcd.text(read_mem(), 80, 66, YELLOW, BLACK, 1)
        lcd.fill_rect(80, 82, 150, 8, BLACK)
        lcd.text(read_uptime(), 80, 82, WHITE, BLACK, 1)
        time.sleep(1)


def main():
    print("ST7789 LCD Demo")
    print("=" * 40)

    try:
        lcd = ST7789()
    except Exception as e:
        print(f"Init failed: {e}")
        sys.exit(1)

    try:
        demo_colour_wash(lcd)
        demo_shapes(lcd)
        demo_text_scales(lcd)
        demo_status_monitor(lcd)
        lcd.fill(BLACK)
        lcd.text("Demo complete.", 10, 10, GREEN, BLACK, 2)
        print("Demo complete.")
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        lcd.close()


if __name__ == "__main__":
    main()
