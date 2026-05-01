#!/usr/bin/env bash
# ================================================================
# setup.sh  -  Radxa Cubie A7A environment preparation
# ================================================================
# Run this script once on the Radxa board to install system
# dependencies, enable the I2C-7 bus, and install the required
# Python packages.
#
# Usage:
#   chmod +x setup.sh
#   sudo ./setup.sh
# ================================================================

set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

echo "========================================"
echo " ISM6HG256X IMU - Environment Setup"
echo "========================================"

# ---- System packages ----
echo "[1/4] Installing system packages ..."
apt-get update -qq
apt-get install -y -qq --no-install-recommends \
    python3 python3-pip python3-venv \
    i2c-tools

# ---- I2C permissions ----
echo "[2/4] Configuring I2C permissions ..."
if ! getent group i2c > /dev/null 2>&1; then
    groupadd i2c
fi
usermod -aG i2c radxa 2>/dev/null || true

# udev rule so /dev/i2c-* is accessible to the i2c group
cat > /etc/udev/rules.d/99-i2c.rules <<'EOF'
KERNEL=="i2c-[0-9]*", GROUP="i2c", MODE="0660"
EOF
udevadm control --reload-rules
udevadm trigger

# ---- Verify I2C-7 is visible ----
echo "[3/4] Verifying I2C-7 bus ..."
if [ -e /dev/i2c-7 ]; then
    echo "  /dev/i2c-7 exists."
    echo "  Scanning for devices ..."
    i2cdetect -y 7 || true
else
    echo "  WARNING: /dev/i2c-7 not found."
    echo "  Enable it via rsetup or device-tree overlay before running the IMU software."
fi

# ---- Python packages ----
echo "[4/4] Installing Python packages ..."
pip3 install --quiet --break-system-packages \
    python-periphery \
    fastapi \
    'uvicorn[standard]' \
    2>/dev/null \
|| pip3 install --quiet \
    python-periphery \
    fastapi \
    'uvicorn[standard]'

echo ""
echo "========================================"
echo " Setup complete."
echo ""
echo " Quick test:"
echo "   python3 ism6hg256x.py"
echo ""
echo " Start dashboard:"
echo "   ./start_dashboard.sh"
echo "========================================"
