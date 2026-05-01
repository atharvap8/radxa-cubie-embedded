#!/usr/bin/env python3
"""
ISM6HG256X I2C Driver
=====================
Low-level register interface and orientation estimator for the
STMicroelectronics ISM6HG256X intelligent 6-axis IMU (low-g accelerometer
and gyroscope channel).

Target platform : Radxa Cubie A7A (Linux, I2C-7)
Transport       : python-periphery over /dev/i2c-7
Reference       : DS15034 datasheet (STMicroelectronics)
"""

import struct
import time
import math

try:
    from periphery import I2C
except ImportError:
    raise ImportError(
        "python-periphery is required.  Install with:  pip install python-periphery"
    )

# ------------------------------------------------------------------ #
#  I2C address (SA0 pin state)
# ------------------------------------------------------------------ #
I2C_ADDR_SA0_LOW  = 0x6A
I2C_ADDR_SA0_HIGH = 0x6B

# ------------------------------------------------------------------ #
#  Register addresses  (standard / UI channel)
# ------------------------------------------------------------------ #
REG_FUNC_CFG_ACCESS = 0x01
REG_WHO_AM_I        = 0x0F
REG_CTRL1_XL        = 0x10   # Accel ODR + mode
REG_CTRL2_G         = 0x11   # Gyro  ODR + FS
REG_CTRL3_C         = 0x12   # Control register 3 (BDU, IF_INC, etc.)
REG_CTRL8           = 0x17   # Accel FS + HPF / LPF2
REG_STATUS          = 0x1E

# Gyroscope output  (little-endian, 6 bytes starting at 0x22)
REG_OUTX_L_G = 0x22

# Accelerometer output  (little-endian, 6 bytes starting at 0x28)
REG_OUTX_L_A = 0x28

# Expected WHO_AM_I value
WHO_AM_I_VALUE = 0x73

# ------------------------------------------------------------------ #
#  ODR settings  (bits [7:4] of CTRL1_XL / CTRL2_G)
#  NOTE: CTRL1_XL bit 2 is the accelerometer enable flag on this
#  device.  It must be OR'd into the register value alongside ODR.
# ------------------------------------------------------------------ #
XL_EN = 0x04  # Accelerometer enable (CTRL1_XL bit 2)
ODR_POWER_DOWN = 0x00
ODR_12_5_HZ    = 0x10
ODR_26_HZ      = 0x20
ODR_52_HZ      = 0x30
ODR_104_HZ     = 0x40
ODR_208_HZ     = 0x50
ODR_416_HZ     = 0x60
ODR_833_HZ     = 0x70
ODR_1660_HZ    = 0x80
ODR_3330_HZ    = 0x90
ODR_6660_HZ    = 0xA0

# ------------------------------------------------------------------ #
#  Accelerometer full-scale  (bits [3:2] of CTRL8)
# ------------------------------------------------------------------ #
FS_XL_2G  = 0x00   # +/- 2 g   -> 0.061 mg/LSB
FS_XL_4G  = 0x04   # +/- 4 g   -> 0.122 mg/LSB
FS_XL_8G  = 0x08   # +/- 8 g   -> 0.244 mg/LSB
FS_XL_16G = 0x0C   # +/- 16 g  -> 0.488 mg/LSB

ACCEL_SENSITIVITY = {
    FS_XL_2G:  0.061,
    FS_XL_4G:  0.122,
    FS_XL_8G:  0.244,
    FS_XL_16G: 0.488,
}

# ------------------------------------------------------------------ #
#  Gyroscope full-scale  (bits [3:0] of CTRL2_G, lower nibble)
# ------------------------------------------------------------------ #
FS_G_250DPS  = 0x00  # +/- 250  dps -> 8.75  mdps/LSB
FS_G_500DPS  = 0x04  # +/- 500  dps -> 17.50 mdps/LSB
FS_G_1000DPS = 0x08  # +/- 1000 dps -> 35.00 mdps/LSB
FS_G_2000DPS = 0x0C  # +/- 2000 dps -> 70.00 mdps/LSB
FS_G_4000DPS = 0x02  # +/- 4000 dps -> 140.0 mdps/LSB

GYRO_SENSITIVITY = {
    FS_G_250DPS:  8.75,
    FS_G_500DPS:  17.50,
    FS_G_1000DPS: 35.00,
    FS_G_2000DPS: 70.00,
    FS_G_4000DPS: 140.00,
}


# ================================================================== #
#  Driver class
# ================================================================== #

class ISM6HG256X:
    """
    I2C driver for the ISM6HG256X IMU.

    Provides raw accelerometer / gyroscope readout in physical units,
    as well as a simple complementary-filter orientation estimator
    (roll, pitch, yaw in degrees).
    """

    def __init__(
        self,
        bus_number: int = 7,
        address: int = I2C_ADDR_SA0_LOW,
        accel_odr: int = ODR_104_HZ,
        gyro_odr: int = ODR_104_HZ,
        accel_fs: int = FS_XL_2G,
        gyro_fs: int = FS_G_1000DPS,
    ):
        """
        Open the I2C bus, verify the device identity, and write the
        initial configuration to the accelerometer and gyroscope
        control registers.

        Parameters
        ----------
        bus_number : int
            Linux I2C bus index (default 7 for /dev/i2c-7).
        address : int
            7-bit I2C slave address (0x6A or 0x6B).
        accel_odr : int
            Output data rate for the accelerometer.
        gyro_odr : int
            Output data rate for the gyroscope.
        accel_fs : int
            Full-scale range for the accelerometer.
        gyro_fs : int
            Full-scale range for the gyroscope.
        """
        self._bus = I2C(f"/dev/i2c-{bus_number}")
        self._addr = address

        self._accel_fs = accel_fs
        self._gyro_fs = gyro_fs
        self._accel_sens = ACCEL_SENSITIVITY[accel_fs]   # mg/LSB
        self._gyro_sens = GYRO_SENSITIVITY[gyro_fs]      # mdps/LSB

        # Verify device identity
        who = self._read_byte(REG_WHO_AM_I)
        if who != WHO_AM_I_VALUE:
            raise RuntimeError(
                f"WHO_AM_I mismatch: expected 0x{WHO_AM_I_VALUE:02X}, "
                f"got 0x{who:02X}.  Check wiring and I2C address."
            )

        # CTRL3_C : enable auto-increment for block reads
        self._write_byte(REG_CTRL3_C, 0x04)

        # Configure accelerometer: ODR + enable bit (bit 2 is
        # mandatory on the ISM6HG256X or the sensor stays idle)
        self._write_byte(REG_CTRL1_XL, accel_odr | XL_EN)

        # Configure accelerometer full-scale in CTRL8
        self._write_byte(REG_CTRL8, accel_fs)

        # Configure gyroscope ODR + full-scale
        self._write_byte(REG_CTRL2_G, gyro_odr | gyro_fs)

        # Allow the sensor to generate at least one sample
        time.sleep(0.1)

        # Orientation estimator state
        self._roll = 0.0
        self._pitch = 0.0
        self._yaw = 0.0
        self._last_time = None

    # -------------------------------------------------------------- #
    #  Low-level I2C helpers
    # -------------------------------------------------------------- #

    def _read_byte(self, reg: int) -> int:
        write_msg = I2C.Message(bytes([reg]), read=False)
        read_msg  = I2C.Message(bytes(1), read=True)
        self._bus.transfer(self._addr, [write_msg, read_msg])
        return read_msg.data[0]

    def _write_byte(self, reg: int, value: int) -> None:
        msg = I2C.Message(bytes([reg, value]), read=False)
        self._bus.transfer(self._addr, [msg])

    def _read_block(self, reg: int, length: int) -> bytes:
        write_msg = I2C.Message(bytes([reg]), read=False)
        read_msg  = I2C.Message(bytes(length), read=True)
        self._bus.transfer(self._addr, [write_msg, read_msg])
        return bytes(read_msg.data)

    # -------------------------------------------------------------- #
    #  Accelerometer
    # -------------------------------------------------------------- #

    def read_accel_raw(self) -> tuple[int, int, int]:
        """Return raw signed 16-bit accelerometer values (x, y, z)."""
        buf = self._read_block(REG_OUTX_L_A, 6)
        x, y, z = struct.unpack('<hhh', buf)
        return x, y, z

    def read_accel(self) -> tuple[float, float, float]:
        """
        Return accelerometer readings in g.

        The raw counts are multiplied by the sensitivity factor
        corresponding to the selected full-scale range, then converted
        from milli-g to g.
        """
        x, y, z = self.read_accel_raw()
        s = self._accel_sens / 1000.0   # mg/LSB -> g/LSB
        return x * s, y * s, z * s

    # -------------------------------------------------------------- #
    #  Gyroscope
    # -------------------------------------------------------------- #

    def read_gyro_raw(self) -> tuple[int, int, int]:
        """Return raw signed 16-bit gyroscope values (x, y, z)."""
        buf = self._read_block(REG_OUTX_L_G, 6)
        x, y, z = struct.unpack('<hhh', buf)
        return x, y, z

    def read_gyro(self) -> tuple[float, float, float]:
        """
        Return gyroscope readings in degrees per second.

        The raw counts are multiplied by the sensitivity factor
        corresponding to the selected full-scale range, then converted
        from milli-dps to dps.
        """
        x, y, z = self.read_gyro_raw()
        s = self._gyro_sens / 1000.0   # mdps/LSB -> dps/LSB
        return x * s, y * s, z * s

    # -------------------------------------------------------------- #
    #  Status
    # -------------------------------------------------------------- #

    def data_ready(self) -> bool:
        """Return True when new accelerometer and gyroscope data is available."""
        status = self._read_byte(REG_STATUS)
        return bool(status & 0x03)

    # -------------------------------------------------------------- #
    #  Orientation estimator  (complementary filter)
    # -------------------------------------------------------------- #

    def update_orientation(self, alpha: float = 0.98) -> tuple[float, float, float]:
        """
        Compute roll, pitch, and yaw using a first-order complementary
        filter that blends the short-term precision of the gyroscope
        with the long-term stability of the accelerometer.

        Parameters
        ----------
        alpha : float
            Gyroscope weighting factor (0..1).  Higher values trust the
            gyroscope more.  Default 0.98.

        Returns
        -------
        tuple of float
            (roll, pitch, yaw) in degrees.
        """
        now = time.monotonic()
        if self._last_time is None:
            self._last_time = now

        dt = now - self._last_time
        self._last_time = now

        ax, ay, az = self.read_accel()
        gx, gy, gz = self.read_gyro()

        # Accelerometer-derived angles (gravity reference)
        accel_roll = math.degrees(math.atan2(ay, az))
        accel_pitch = math.degrees(
            math.atan2(-ax, math.sqrt(ay * ay + az * az))
        )

        # Integrate gyroscope
        self._roll += gx * dt
        self._pitch += gy * dt
        self._yaw += gz * dt

        # Complementary blend
        self._roll = alpha * self._roll + (1.0 - alpha) * accel_roll
        self._pitch = alpha * self._pitch + (1.0 - alpha) * accel_pitch
        # Yaw has no absolute reference from the accelerometer alone
        # and drifts over time; this is inherent to 6-axis IMUs.

        return self._roll, self._pitch, self._yaw

    def reset_orientation(self) -> None:
        """Reset the internal orientation state to zero."""
        self._roll = 0.0
        self._pitch = 0.0
        self._yaw = 0.0
        self._last_time = None

    # -------------------------------------------------------------- #
    #  Lifecycle
    # -------------------------------------------------------------- #

    def power_down(self) -> None:
        """Place both sensors into power-down mode."""
        self._write_byte(REG_CTRL1_XL, ODR_POWER_DOWN)
        self._write_byte(REG_CTRL2_G, ODR_POWER_DOWN)

    def close(self) -> None:
        """Power down the sensors and release the I2C bus."""
        self.power_down()
        self._bus.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


# ================================================================== #
#  Self-test / stand-alone diagnostic
# ================================================================== #

def main():
    """Quick diagnostic: print sensor readings to the terminal."""
    print("ISM6HG256X I2C Driver - Diagnostic Mode")
    print("=" * 50)

    try:
        imu = ISM6HG256X(bus_number=7, address=I2C_ADDR_SA0_LOW)
    except Exception as e:
        print(f"Initialisation failed: {e}")
        return

    who = imu._read_byte(REG_WHO_AM_I)
    print(f"WHO_AM_I : 0x{who:02X}  (expected 0x{WHO_AM_I_VALUE:02X})")
    print(f"Accel FS : +/- {[2,4,8,16][[FS_XL_2G, FS_XL_4G, FS_XL_8G, FS_XL_16G].index(imu._accel_fs)]} g")
    print(f"Gyro  FS : configured")
    print("-" * 50)

    try:
        while True:
            ax, ay, az = imu.read_accel()
            gx, gy, gz = imu.read_gyro()
            roll, pitch, yaw = imu.update_orientation()
            print(
                f"\rAccel: {ax:+7.3f} {ay:+7.3f} {az:+7.3f} g  |  "
                f"Gyro: {gx:+8.2f} {gy:+8.2f} {gz:+8.2f} dps  |  "
                f"RPY: {roll:+7.2f} {pitch:+7.2f} {yaw:+7.2f} deg",
                end="", flush=True,
            )
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("\n\nStopped by user.")
    finally:
        imu.close()


if __name__ == "__main__":
    main()
