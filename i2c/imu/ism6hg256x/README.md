# ISM6HG256X I2C IMU Driver

Register-level I2C driver for the ISM6HG256X 6-axis inertial
measurement unit (accelerometer + gyroscope), implemented in Python
using `python-periphery`.

## Hardware

| Parameter       | Value                                       |
|-----------------|---------------------------------------------|
| Device          | ISM6HG256X (STMicroelectronics)             |
| Accelerometer   | 3-axis, configurable FS (2/4/8/16 g)       |
| Gyroscope       | 3-axis, configurable FS (250..4000 dps)     |
| Interface       | I2C (7-bit address 0x6A or 0x6B)            |
| Bus             | I2C-7 on the Radxa Cubie A7A                |

## Device-specific notes

The ISM6HG256X has several register behaviours that differ from
other ST IMU devices in the ISM330 family:

1. **CTRL1_XL bit 2 (XL_EN)** must be set alongside the ODR bits,
   or the accelerometer will never produce new data.  The STATUS
   register XLDA flag remains zero without this bit.

2. **Accelerometer full-scale** is configured via CTRL8 (0x17),
   not via CTRL1_XL bits [3:2] as on most ST IMUs.

3. **Gyroscope full-scale** is encoded in the lower nibble of
   CTRL2_G alongside the ODR, which is the standard ST layout.

These findings were determined empirically through live register
probing on hardware, as the full datasheet for this device is not
publicly available.

## Wiring

| IMU Pin | Radxa Pin    | Notes                          |
|---------|--------------|--------------------------------|
| VCC     | 3.3 V        |                                |
| GND     | GND          |                                |
| SDA     | I2C7_SDA     | 4.7 kΩ pull-up to 3.3 V       |
| SCL     | I2C7_SCL     | 4.7 kΩ pull-up to 3.3 V       |
| SA0     | GND or VCC   | Sets bit 0 of the I2C address  |

## Prerequisites

1. I2C-7 must be enabled.  Verify with:
   ```
   ls /dev/i2c-7
   i2cdetect -y 7
   ```
   The device should appear at address 0x6A (SA0 = GND) or
   0x6B (SA0 = VCC).

2. The `radxa` user must have permission to access the bus:
   ```
   sudo usermod -aG i2c radxa
   ```

## Quick start

```python
from ism6hg256x import ISM6HG256X

imu = ISM6HG256X(bus_number=7)
ax, ay, az = imu.read_accel_g()
gx, gy, gz = imu.read_gyro_dps()
roll, pitch, yaw = imu.update_orientation()
imu.close()
```

## Headless streaming

`imu_stream.py` runs a continuous console readout at approximately
50 Hz, printing accelerometer, gyroscope, and orientation data:

```
python3 imu_stream.py
```

## Sensitivity constants

| Accel FS | Sensitivity (mg/LSB) | Gyro FS   | Sensitivity (mdps/LSB) |
|----------|----------------------|-----------|------------------------|
| ±2 g     | 0.061                | ±250 dps  | 8.75                   |
| ±4 g     | 0.122                | ±500 dps  | 17.50                  |
| ±8 g     | 0.244                | ±1000 dps | 35.00                  |
| ±16 g    | 0.488                | ±2000 dps | 70.00                  |
|          |                      | ±4000 dps | 140.00                 |

## Dependencies

```
pip install python-periphery
```
