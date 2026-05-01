#!/usr/bin/env python3
"""
ST7789 SPI LCD Driver
=====================
Register-level SPI driver for the ST7789V 240x320 non-touch TFT LCD
using python-periphery.

Hardware
--------
- Controller : ST7789V
- Resolution : 240 x 320, 16-bit RGB565
- Interface  : SPI (write-only: MOSI + SCLK + CS)
- Control    : GPIO for DC, RST, BL

Wiring (directly to Radxa Cubie A7A 40-pin header)
---------------------------------------------------
  LCD Pin   Radxa Pin   Description
  VCC       3.3 V       Supply (do NOT use 5 V)
  GND       GND         Ground
  CS        SPI1_CS0    Chip select
  RESET     GPIOx       Hardware reset (configurable)
  DC/RS     GPIOx       Data / Command select
  SDA       SPI1_MOSI   Serial data
  SCK       SPI1_SCLK   Serial clock
  LED       GPIOx       Backlight enable (or 3.3 V for always-on)
"""

import time
import struct
from periphery import SPI, GPIO

# ------------------------------------------------------------------ #
#  ST7789 Command Set
# ------------------------------------------------------------------ #
_SWRESET = 0x01
_SLPOUT  = 0x11
_NORON   = 0x13
_INVON   = 0x21
_DISPOFF = 0x28
_DISPON  = 0x29
_CASET   = 0x2A
_RASET   = 0x2B
_RAMWR   = 0x2C
_MADCTL  = 0x36
_COLMOD  = 0x3A

# MADCTL flags
_MY  = 0x80
_MX  = 0x40
_MV  = 0x20
_BGR = 0x08

# Rotation -> (MADCTL value, width, height)
_ROTATIONS = {
    0:   (_MX | _BGR,       240, 320),
    90:  (_MV | _BGR,       320, 240),
    180: (_MY | _BGR,       240, 320),
    270: (_MV | _MX | _MY | _BGR, 320, 240),
}

# ------------------------------------------------------------------ #
#  RGB565 Colour Constants
# ------------------------------------------------------------------ #
BLACK      = 0x0000
WHITE      = 0xFFFF
RED        = 0xF800
GREEN      = 0x07E0
BLUE       = 0x001F
CYAN       = 0x07FF
MAGENTA    = 0xF81F
YELLOW     = 0xFFE0
ORANGE     = 0xFD20
PURPLE     = 0x801F
GRAY       = 0x8410
DARK_GRAY  = 0x4208
LIGHT_GRAY = 0xC618


def color565(r: int, g: int, b: int) -> int:
    """Convert 8-bit RGB components to a 16-bit RGB565 value."""
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


# ------------------------------------------------------------------ #
#  Embedded 5x7 bitmap font  (ASCII 0x20 .. 0x7E)
#  Each glyph is 5 bytes; each byte is one column, LSB = top row.
# ------------------------------------------------------------------ #
_FONT = (
    b'\x00\x00\x00\x00\x00'  # 0x20 space
    b'\x00\x00\x5F\x00\x00'  # !
    b'\x00\x07\x00\x07\x00'  # "
    b'\x14\x7F\x14\x7F\x14'  # #
    b'\x24\x2A\x7F\x2A\x12'  # $
    b'\x23\x13\x08\x64\x62'  # %
    b'\x36\x49\x55\x22\x50'  # &
    b'\x00\x05\x03\x00\x00'  # '
    b'\x00\x1C\x22\x41\x00'  # (
    b'\x00\x41\x22\x1C\x00'  # )
    b'\x14\x08\x3E\x08\x14'  # *
    b'\x08\x08\x3E\x08\x08'  # +
    b'\x00\x50\x30\x00\x00'  # ,
    b'\x08\x08\x08\x08\x08'  # -
    b'\x00\x60\x60\x00\x00'  # .
    b'\x20\x10\x08\x04\x02'  # /
    b'\x3E\x51\x49\x45\x3E'  # 0
    b'\x00\x42\x7F\x40\x00'  # 1
    b'\x42\x61\x51\x49\x46'  # 2
    b'\x21\x41\x45\x4B\x31'  # 3
    b'\x18\x14\x12\x7F\x10'  # 4
    b'\x27\x45\x45\x45\x39'  # 5
    b'\x3C\x4A\x49\x49\x30'  # 6
    b'\x01\x71\x09\x05\x03'  # 7
    b'\x36\x49\x49\x49\x36'  # 8
    b'\x06\x49\x49\x29\x1E'  # 9
    b'\x00\x36\x36\x00\x00'  # :
    b'\x00\x56\x36\x00\x00'  # ;
    b'\x08\x14\x22\x41\x00'  # <
    b'\x14\x14\x14\x14\x14'  # =
    b'\x00\x41\x22\x14\x08'  # >
    b'\x02\x01\x51\x09\x06'  # ?
    b'\x32\x49\x79\x41\x3E'  # @
    b'\x7E\x11\x11\x11\x7E'  # A
    b'\x7F\x49\x49\x49\x36'  # B
    b'\x3E\x41\x41\x41\x22'  # C
    b'\x7F\x41\x41\x22\x1C'  # D
    b'\x7F\x49\x49\x49\x41'  # E
    b'\x7F\x09\x09\x09\x01'  # F
    b'\x3E\x41\x49\x49\x7A'  # G
    b'\x7F\x08\x08\x08\x7F'  # H
    b'\x00\x41\x7F\x41\x00'  # I
    b'\x20\x40\x41\x3F\x01'  # J
    b'\x7F\x08\x14\x22\x41'  # K
    b'\x7F\x40\x40\x40\x40'  # L
    b'\x7F\x02\x0C\x02\x7F'  # M
    b'\x7F\x04\x08\x10\x7F'  # N
    b'\x3E\x41\x41\x41\x3E'  # O
    b'\x7F\x09\x09\x09\x06'  # P
    b'\x3E\x41\x51\x21\x5E'  # Q
    b'\x7F\x09\x19\x29\x46'  # R
    b'\x46\x49\x49\x49\x31'  # S
    b'\x01\x01\x7F\x01\x01'  # T
    b'\x3F\x40\x40\x40\x3F'  # U
    b'\x1F\x20\x40\x20\x1F'  # V
    b'\x3F\x40\x38\x40\x3F'  # W
    b'\x63\x14\x08\x14\x63'  # X
    b'\x07\x08\x70\x08\x07'  # Y
    b'\x61\x51\x49\x45\x43'  # Z
    b'\x00\x7F\x41\x41\x00'  # [
    b'\x02\x04\x08\x10\x20'  # backslash
    b'\x00\x41\x41\x7F\x00'  # ]
    b'\x04\x02\x01\x02\x04'  # ^
    b'\x40\x40\x40\x40\x40'  # _
    b'\x00\x01\x02\x04\x00'  # `
    b'\x20\x54\x54\x54\x78'  # a
    b'\x7F\x48\x44\x44\x38'  # b
    b'\x38\x44\x44\x44\x20'  # c
    b'\x38\x44\x44\x48\x7F'  # d
    b'\x38\x54\x54\x54\x18'  # e
    b'\x08\x7E\x09\x01\x02'  # f
    b'\x0C\x52\x52\x52\x3E'  # g
    b'\x7F\x08\x04\x04\x78'  # h
    b'\x00\x44\x7D\x40\x00'  # i
    b'\x20\x40\x44\x3D\x00'  # j
    b'\x7F\x10\x28\x44\x00'  # k
    b'\x00\x41\x7F\x40\x00'  # l
    b'\x7C\x04\x18\x04\x78'  # m
    b'\x7C\x08\x04\x04\x78'  # n
    b'\x38\x44\x44\x44\x38'  # o
    b'\x7C\x14\x14\x14\x08'  # p
    b'\x08\x14\x14\x18\x7C'  # q
    b'\x7C\x08\x04\x04\x08'  # r
    b'\x48\x54\x54\x54\x20'  # s
    b'\x04\x3F\x44\x40\x20'  # t
    b'\x3C\x40\x40\x20\x7C'  # u
    b'\x1C\x20\x40\x20\x1C'  # v
    b'\x3C\x40\x30\x40\x3C'  # w
    b'\x44\x28\x10\x28\x44'  # x
    b'\x0C\x50\x50\x50\x3C'  # y
    b'\x44\x64\x54\x4C\x44'  # z
    b'\x00\x08\x36\x41\x00'  # {
    b'\x00\x00\x7F\x00\x00'  # |
    b'\x00\x41\x36\x08\x00'  # }
    b'\x10\x08\x08\x10\x10'  # ~
)

_SPI_CHUNK = 4096  # max bytes per SPI transfer


# ================================================================== #
#  Driver
# ================================================================== #

class ST7789:
    """SPI driver for ST7789V-based 240x320 TFT LCD panels."""

    def __init__(
        self,
        spi_dev: str = "/dev/spidev1.0",
        speed_hz: int = 40_000_000,
        dc_chip: str = "/dev/gpiochip0",
        dc_line: int = 25,
        rst_chip: str = "/dev/gpiochip0",
        rst_line: int = 26,
        bl_chip: str | None = "/dev/gpiochip0",
        bl_line: int | None = 27,
        width: int = 240,
        height: int = 320,
        rotation: int = 0,
    ):
        self._spi = SPI(spi_dev, 0, speed_hz)  # mode 0
        self._dc  = GPIO(dc_chip, dc_line, "out", inverted=False)
        self._rst = GPIO(rst_chip, rst_line, "out", inverted=False)
        self._bl  = GPIO(bl_chip, bl_line, "out") if bl_chip and bl_line is not None else None

        if rotation not in _ROTATIONS:
            raise ValueError(f"rotation must be one of {list(_ROTATIONS)}")
        madctl, self.width, self.height = _ROTATIONS[rotation]
        self._madctl = madctl

        self._init_display()

    # ------------------------------------------------------------ #
    #  Initialisation
    # ------------------------------------------------------------ #

    def _init_display(self):
        self._hard_reset()
        self._cmd(_SWRESET)
        time.sleep(0.15)
        self._cmd(_SLPOUT)
        time.sleep(0.5)
        self._cmd(_COLMOD, bytes([0x55]))       # 16-bit colour
        self._cmd(_MADCTL, bytes([self._madctl]))
        self._cmd(_INVON)                       # ST7789 needs inversion
        self._cmd(_NORON)
        time.sleep(0.01)
        self._cmd(_DISPON)
        time.sleep(0.1)
        self.backlight(True)

    def _hard_reset(self):
        self._rst.write(True)
        time.sleep(0.01)
        self._rst.write(False)
        time.sleep(0.01)
        self._rst.write(True)
        time.sleep(0.12)

    # ------------------------------------------------------------ #
    #  Low-level SPI helpers
    # ------------------------------------------------------------ #

    def _cmd(self, command: int, data: bytes | None = None):
        self._dc.write(False)
        self._spi.transfer(bytes([command]))
        if data:
            self._dc.write(True)
            self._write(data)

    def _write(self, data: bytes | bytearray | memoryview):
        self._dc.write(True)
        mv = memoryview(data) if not isinstance(data, memoryview) else data
        for i in range(0, len(mv), _SPI_CHUNK):
            self._spi.transfer(bytes(mv[i:i + _SPI_CHUNK]))

    # ------------------------------------------------------------ #
    #  Window addressing
    # ------------------------------------------------------------ #

    def _set_window(self, x0: int, y0: int, x1: int, y1: int):
        self._cmd(_CASET, struct.pack(">HH", x0, x1))
        self._cmd(_RASET, struct.pack(">HH", y0, y1))
        self._cmd(_RAMWR)

    # ------------------------------------------------------------ #
    #  Drawing primitives
    # ------------------------------------------------------------ #

    def fill(self, color: int = BLACK):
        """Fill the entire screen with a solid colour."""
        self._set_window(0, 0, self.width - 1, self.height - 1)
        px = struct.pack(">H", color) * min(self.width, 240)
        for _ in range(self.height):
            self._write(px)

    def fill_rect(self, x: int, y: int, w: int, h: int, color: int):
        """Fill a rectangle at (x, y) with dimensions w x h."""
        x1 = min(x + w - 1, self.width - 1)
        y1 = min(y + h - 1, self.height - 1)
        self._set_window(x, y, x1, y1)
        row = struct.pack(">H", color) * (x1 - x + 1)
        for _ in range(y1 - y + 1):
            self._write(row)

    def pixel(self, x: int, y: int, color: int):
        """Set a single pixel."""
        if 0 <= x < self.width and 0 <= y < self.height:
            self._set_window(x, y, x, y)
            self._write(struct.pack(">H", color))

    def hline(self, x: int, y: int, w: int, color: int):
        """Horizontal line."""
        self.fill_rect(x, y, w, 1, color)

    def vline(self, x: int, y: int, h: int, color: int):
        """Vertical line."""
        self.fill_rect(x, y, 1, h, color)

    def rect(self, x: int, y: int, w: int, h: int, color: int):
        """Draw a rectangle outline."""
        self.hline(x, y, w, color)
        self.hline(x, y + h - 1, w, color)
        self.vline(x, y, h, color)
        self.vline(x + w - 1, y, h, color)

    def line(self, x0: int, y0: int, x1: int, y1: int, color: int):
        """Bresenham line between two points."""
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self.pixel(x0, y0, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def circle(self, cx: int, cy: int, r: int, color: int):
        """Midpoint circle outline."""
        x, y, d = 0, r, 1 - r
        while x <= y:
            for sx, sy in ((1,1),(1,-1),(-1,1),(-1,-1)):
                self.pixel(cx + sx * x, cy + sy * y, color)
                self.pixel(cx + sx * y, cy + sy * x, color)
            x += 1
            if d < 0:
                d += 2 * x + 1
            else:
                y -= 1
                d += 2 * (x - y) + 1

    # ------------------------------------------------------------ #
    #  Text rendering
    # ------------------------------------------------------------ #

    def char(self, ch: str, x: int, y: int, color: int,
             bg: int | None = None, scale: int = 1):
        """Render a single character at (x, y). Returns advance width."""
        idx = ord(ch) - 0x20
        if idx < 0 or idx >= 95:
            idx = 0  # default to space
        glyph = _FONT[idx * 5:(idx + 1) * 5]
        for col in range(5):
            for row in range(7):
                c = color if glyph[col] & (1 << row) else bg
                if c is not None:
                    if scale == 1:
                        self.pixel(x + col, y + row, c)
                    else:
                        self.fill_rect(x + col * scale, y + row * scale,
                                       scale, scale, c)
        # column gap
        if bg is not None:
            if scale == 1:
                self.vline(x + 5, y, 7, bg)
            else:
                self.fill_rect(x + 5 * scale, y, scale, 7 * scale, bg)
        return 6 * scale

    def text(self, string: str, x: int, y: int, color: int = WHITE,
             bg: int | None = None, scale: int = 1):
        """Render a string. Wraps at screen edge."""
        ox = x
        for ch in string:
            if ch == '\n' or x + 6 * scale > self.width:
                x = ox
                y += 8 * scale
                if ch == '\n':
                    continue
            x += self.char(ch, x, y, color, bg, scale)

    # ------------------------------------------------------------ #
    #  Framebuffer / image blit
    # ------------------------------------------------------------ #

    def blit(self, x: int, y: int, w: int, h: int, data: bytes):
        """Write raw RGB565 pixel data (big-endian) into a region."""
        self._set_window(x, y, x + w - 1, y + h - 1)
        self._write(data)

    # ------------------------------------------------------------ #
    #  Backlight and lifecycle
    # ------------------------------------------------------------ #

    def backlight(self, on: bool = True):
        if self._bl:
            self._bl.write(on)

    def sleep(self):
        """Enter sleep mode (low power)."""
        self._cmd(_DISPOFF)
        time.sleep(0.01)
        self._cmd(0x10)  # SLPIN
        self.backlight(False)

    def wake(self):
        """Exit sleep mode."""
        self._cmd(_SLPOUT)
        time.sleep(0.5)
        self._cmd(_DISPON)
        self.backlight(True)

    def close(self):
        """Power down and release hardware resources."""
        self.backlight(False)
        self._cmd(_DISPOFF)
        self._spi.close()
        self._dc.close()
        self._rst.close()
        if self._bl:
            self._bl.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


# ------------------------------------------------------------------ #
#  Standalone diagnostic
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    import sys

    print("ST7789 SPI LCD Driver - Diagnostic Mode")
    print("=" * 50)

    try:
        lcd = ST7789()
    except Exception as e:
        print(f"Failed to initialise: {e}")
        print("Check SPI overlay, wiring, and GPIO pin numbers.")
        sys.exit(1)

    try:
        lcd.fill(BLACK)
        lcd.text("ST7789 240x320", 10, 10, WHITE, BLACK, 2)
        lcd.text("Radxa Cubie A7A", 10, 40, CYAN, BLACK, 1)
        lcd.text("SPI LCD OK", 10, 56, GREEN, BLACK, 1)

        # Colour bars
        colours = [RED, GREEN, BLUE, YELLOW, CYAN, MAGENTA, WHITE]
        bw = lcd.width // len(colours)
        for i, c in enumerate(colours):
            lcd.fill_rect(i * bw, 80, bw, 40, c)

        lcd.rect(5, 130, 230, 80, PURPLE)
        lcd.line(5, 130, 234, 209, ORANGE)
        lcd.circle(120, 260, 30, RED)

        print("Display test pattern rendered.")
        print("Press Ctrl+C to exit.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        lcd.close()
        print("Done.")
