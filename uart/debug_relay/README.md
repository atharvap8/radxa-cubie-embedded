# UART Debug Relay

Bidirectional debug log relay over UART between the Radxa Cubie A7A
and a remote host (PC, microcontroller, or another SBC).

## Architecture

```
 Radxa Cubie A7A                    Remote Host
 ┌──────────────┐    UART (TX/RX)   ┌──────────────┐
 │ uart_relay.py │ ──────────────── │uart_receiver.py│
 │               │                   │               │
 │  journalctl   │ ── [LOG] ──────> │  terminal     │
 │               │                   │  display      │
 │  shell exec   │ <── command ──── │  keyboard     │
 │               │ ── [RSP] ──────> │  input        │
 └──────────────┘                   └──────────────┘
```

## Wire Protocol

All communication is text-based, newline-delimited, and UTF-8 encoded.

| Direction      | Format                    | Description                   |
|----------------|---------------------------|-------------------------------|
| Radxa -> Remote| `[LOG] <message>\n`       | System log line               |
| Remote -> Radxa| `<command>\n`             | Shell command to execute      |
| Radxa -> Remote| `[RSP]\n<output>\n[/RSP]\n`| Command execution result    |

## Wiring

| Radxa Pin | Remote Pin | Notes                         |
|-----------|------------|-------------------------------|
| UART TX   | RX         | Cross-connect                 |
| UART RX   | TX         | Cross-connect                 |
| GND       | GND        | Common ground                 |

The default UART device is `/dev/ttyS2`.  Determine the correct
device for your board by checking which UART is exposed on the
40-pin header.  Enable the UART overlay via `rsetup` if necessary.

If connecting to a PC, use a 3.3 V USB-to-UART adapter (CP2102,
CH340, FT232R, or similar).  Do not use 5 V logic levels.

## Usage

### Radxa side

```bash
cd ~/embedded/uart/debug_relay
source venv/bin/activate
python3 uart_relay.py -p /dev/ttyS2 -b 115200
```

### PC side

```bash
pip install pyserial
python3 uart_receiver.py -p /dev/ttyUSB0 -b 115200
```

Type a command in the receiver terminal and press Enter.  The Radxa
will execute it and send the output back, displayed between
`--- response start ---` and `--- response end ---` markers.

## Dependencies

| Side  | Package            | Install                       |
|-------|--------------------|-------------------------------|
| Radxa | python-periphery   | `pip install python-periphery`|
| PC    | pyserial           | `pip install pyserial`        |

## Security notice

The relay executes arbitrary shell commands received over UART.
This is intended for development and debugging on a local bench.
Do not expose the UART port in a production or untrusted environment.
