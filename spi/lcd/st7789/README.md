# ST7789 SPI LCD Driver

Register-level SPI driver for the ST7789V 240x320 non-touch TFT LCD,
implemented in Python using `python-periphery`.

## Hardware

| Parameter   | Value                    |
|-------------|--------------------------|
| Controller  | ST7789V                  |
| Resolution  | 240 x 320 px             |
| Colour      | 16-bit RGB565            |
| Interface   | SPI (mode 0, write-only) |
| Supply      | 3.3 V                    |
| Touch       | None                     |

## Wiring

Connect the LCD to the Radxa Cubie A7A 40-pin header as follows.
The exact GPIO chip and line numbers depend on the board device-tree
overlay in use; the values below are placeholders and must be adjusted
to match the physical pins you choose.

| LCD Pin | Connect to         | Notes                          |
|---------|--------------------|--------------------------------|
| VCC     | 3.3 V              | Do not use 5 V                 |
| GND     | GND                |                                |
| CS      | SPI1_CS0           | Hardware chip select           |
| RESET   | GPIO (configurable)| Hardware reset line            |
| DC/RS   | GPIO (configurable)| Data / Command select          |
| SDA     | SPI1_MOSI          | Serial data                    |
| SCK     | SPI1_SCLK          | Serial clock                   |
| LED     | GPIO (configurable)| Backlight (or tie to 3.3 V)    |

## Prerequisites

1. Enable the SPI1 overlay on the Radxa via `rsetup` or by editing
   `/boot/uEnv.txt`.  After a reboot, `/dev/spidev1.0` should appear.

2. Install the Python dependency:
   ```
   pip install python-periphery
   ```

3. Determine the GPIO chip and line numbers for your DC, RST, and BL
   pins using `gpioinfo`:
   ```
   sudo gpioinfo
   ```

## Quick start

```python
from st7789 import ST7789, RED, WHITE

lcd = ST7789(
    spi_dev="/dev/spidev1.0",
    dc_chip="/dev/gpiochip0",  dc_line=25,
    rst_chip="/dev/gpiochip0", rst_line=26,
    bl_chip="/dev/gpiochip0",  bl_line=27,
)

lcd.fill(RED)
lcd.text("Hello", 10, 10, WHITE, RED, 3)
lcd.close()
```

## Demo

```
python3 lcd_demo.py
```

Runs a sequence of visual tests: colour fills, geometric shapes,
text at various scales, and a live system monitor showing CPU
temperature, memory usage, and uptime.

## API overview

| Method                          | Description                           |
|---------------------------------|---------------------------------------|
| `fill(color)`                   | Solid screen fill                     |
| `fill_rect(x, y, w, h, color)` | Filled rectangle                      |
| `pixel(x, y, color)`           | Single pixel                          |
| `hline / vline`                 | Horizontal / vertical line            |
| `line(x0, y0, x1, y1, color)`  | Bresenham line                        |
| `rect(x, y, w, h, color)`      | Rectangle outline                     |
| `circle(cx, cy, r, color)`     | Circle outline (midpoint algorithm)   |
| `text(str, x, y, color, bg, s)`| Render string (embedded 5x7 font)     |
| `blit(x, y, w, h, data)`       | Write raw RGB565 framebuffer          |
| `backlight(on)`                 | Toggle backlight GPIO                 |
| `sleep() / wake()`              | Enter / exit low-power mode           |
| `close()`                       | Release SPI and GPIO resources        |

## Colour helpers

```python
from st7789 import color565, BLACK, WHITE, RED, GREEN, BLUE
custom = color565(128, 0, 255)   # purple
```
