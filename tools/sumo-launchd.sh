#!/usr/bin/env bash
# MultiRATVANET - start the Veins TraCI launch daemon that the simulation connects to.
# For every simulation that connects, the daemon starts a SUMO instance on the scenario the
# simulation names (*.veinsManager.launchConfig). Leave it running in its own terminal.
# Not needed with Docker: the image starts its own daemon.
#
# Usage: ./tools/sumo-launchd.sh [PORT] [SUMO_BINARY]
#   PORT         TCP port the simulation connects to; must match *.veinsManager.port (default 9999)
#   SUMO_BINARY  sumo (headless, default) | sumo-gui
#
# Environment: VEINS_DIR (default /home/vnet/vehicular-sim/veins-5.3.1).
# Only one daemon can own a port.
set -e

PORT="${1:-9999}"
SUMO_BIN="${2:-sumo}"
VEINS_DIR="${VEINS_DIR:-/home/vnet/vehicular-sim/veins-5.3.1}"
LAUNCHD="$VEINS_DIR/bin/veins_launchd"

[ -f "$LAUNCHD" ] || { echo "ERROR: $LAUNCHD not found; set VEINS_DIR" >&2; exit 1; }
command -v "$SUMO_BIN" >/dev/null || { echo "ERROR: $SUMO_BIN not on PATH" >&2; exit 1; }

echo "=== veins_launchd on port $PORT using $SUMO_BIN (Ctrl+C to stop)"
exec python3 "$LAUNCHD" -vv -c "$SUMO_BIN" -p "$PORT"
