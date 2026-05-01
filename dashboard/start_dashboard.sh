#!/usr/bin/env bash
# Start the Radxa Cubie A7A Dashboard
# Accessible at http://192.168.1.66:8080

set -euo pipefail
cd "$(dirname "$0")"

echo "Starting dashboard server ..."
echo "  URL:  http://192.168.1.66:8080"
echo ""

exec python3 server.py
