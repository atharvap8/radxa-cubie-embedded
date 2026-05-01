# Radxa Cubie A7A Embedded Workspace

Peripheral drivers, tools, and a browser-based dashboard for the
Radxa Cubie A7A single-board computer.

## Repository layout

```
embedded/
├── i2c/
│   └── imu/
│       └── ism6hg256x/         ISM6HG256X 6-axis IMU driver (I2C)
│           ├── ism6hg256x.py   Register-level driver
│           ├── imu_stream.py   Headless console streamer
│           └── README.md
│
├── spi/
│   └── lcd/
│       └── st7789/             ST7789V 240x320 LCD driver (SPI)
│           ├── st7789.py       Register-level driver
│           ├── lcd_demo.py     Visual demo application
│           └── README.md
│
├── uart/
│   └── debug_relay/            Bidirectional UART debug relay
│       ├── uart_relay.py       Radxa side (log forwarding + command exec)
│       ├── uart_receiver.py    PC side (display + interactive input)
│       └── README.md
│
├── dashboard/                  Browser-based command centre
│   ├── server.py               FastAPI backend
│   ├── static/                 Frontend (HTML / CSS / JS)
│   └── README.md
│
├── setup.sh                    Board environment setup script
└── README.md                   This file
```

## Hardware summary

| Peripheral   | Device       | Bus    | Driver location            |
|--------------|--------------|--------|----------------------------|
| IMU          | ISM6HG256X   | I2C-7  | `i2c/imu/ism6hg256x/`     |
| LCD          | ST7789V      | SPI1   | `spi/lcd/st7789/`         |
| Debug log    | UART adapter | UART   | `uart/debug_relay/`        |
| Dashboard    | Web server   | TCP    | `dashboard/`               |

## Board setup

Run the setup script once after cloning:

```bash
chmod +x setup.sh
./setup.sh
```

This configures I2C permissions, creates a Python virtual
environment, and installs the required packages.

For SPI and UART peripherals, enable the corresponding overlays
via `rsetup` and reboot.

## Per-module documentation

Each subdirectory contains its own README with wiring diagrams,
API reference, and usage instructions.  Refer to:

- [IMU Driver](i2c/imu/ism6hg256x/README.md)
- [LCD Driver](spi/lcd/st7789/README.md)
- [UART Relay](uart/debug_relay/README.md)
- [Dashboard](dashboard/README.md)

## Dependencies

All drivers use `python-periphery` for direct hardware access via
standard Linux kernel interfaces (I2C cdev, SPI devfs, GPIO cdev,
serial tty).  The dashboard additionally requires `fastapi` and
`uvicorn`.

```bash
pip install python-periphery fastapi 'uvicorn[standard]'
```

## Deployment

From a development machine, deploy the entire workspace to the
Radxa:

```bash
rsync -avz --exclude='__pycache__' --exclude='.git' \
    ./ radxa@192.168.1.66:~/embedded/
```

Or deploy individual modules:

```bash
scp -r spi/lcd/st7789/ radxa@192.168.1.66:~/embedded/spi/lcd/st7789/
```
