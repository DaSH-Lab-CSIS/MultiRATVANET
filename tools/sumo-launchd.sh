#!/usr/bin/env bash
# ============================================================================
# MultiRATVANET - Veins SUMO launch daemon
# ----------------------------------------------------------------------------
# Starts the Veins TraCI launch daemon that OMNeT++/Veins connects to. When the
# simulation connects, the daemon spawns a SUMO instance bound to the scenario
# supplied by the model (via *.veinsManager.launchConfig).
#
# Usage:
#   ./sumo-launchd.sh [PORT] [SUMO_BINARY]
#     PORT         TCP port OMNeT++/Veins connects to        (default 9998)
#     SUMO_BINARY  sumo.exe (headless) | sumo-gui.exe (GUI)  (default sumo-gui.exe)
#
# Examples:
#   ./sumo-launchd.sh                 # GUI daemon on 9998
#   ./sumo-launchd.sh 9998 sumo.exe   # headless daemon on 9998
#
# Only ONE daemon may own a port at a time.
# ============================================================================
set -e

PORT="${1:-9998}"
SUMO_BIN="${2:-sumo-gui.exe}"

PROJ_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # repo root
VEINS="$PROJ_DIR/external/veins-5.2"
LAUNCHD="$VEINS/bin/veins_launchd"
[ -f "$LAUNCHD" ] || LAUNCHD="$VEINS/sumo-launchd.py"

# Resolve SUMO_HOME so veins_launchd can find the SUMO binary.
if [ -z "$SUMO_HOME" ]; then
    for c in \
        "/c/Program Files (x86)/Eclipse/Sumo" \
        "/c/Program Files/Eclipse/Sumo" \
        "$PROJ_DIR/../sumo-1_24_0"; do
        if [ -f "$c/bin/$SUMO_BIN" ]; then SUMO_HOME="$c"; break; fi
    done
fi

# SUMO_HOME may be pre-set in Windows form (C:\...). Normalize to a POSIX path
# for PATH manipulation; keep a Windows form for the SUMO_HOME env var itself.
SUMO_HOME_POSIX="$(cygpath -u "$SUMO_HOME" 2>/dev/null || echo "$SUMO_HOME")"

if [ -z "$SUMO_HOME_POSIX" ] || [ ! -f "$SUMO_HOME_POSIX/bin/$SUMO_BIN" ]; then
    echo "ERROR: could not locate $SUMO_BIN. Set SUMO_HOME to your SUMO install," >&2
    echo "       e.g. export SUMO_HOME='/c/Program Files (x86)/Eclipse/Sumo'"       >&2
    exit 1
fi

export SUMO_HOME="$(cygpath -w "$SUMO_HOME_POSIX" 2>/dev/null || echo "$SUMO_HOME_POSIX")"
# Put the SUMO bin dir on PATH in POSIX form so the daemon can spawn sumo.exe.
export PATH="$SUMO_HOME_POSIX/bin:$PATH"

echo "=== SUMO_HOME = $SUMO_HOME"
echo "=== SUMO bin  = $SUMO_HOME_POSIX/bin"
echo "=== launch daemon on port $PORT using $SUMO_BIN"
echo "=== (Ctrl+C to stop; only one daemon per port)"

# Run from the repo root so the launchd <basedir> (simulations/scenarios/...)
# resolves the same way the OMNeT++ launchConfig path does.
cd "$PROJ_DIR"

# -c command, -p port, -vv verbose. Daemon stays in the foreground and spawns a
# fresh SUMO for every incoming OMNeT++ connection.
python "$LAUNCHD" -vv -c "$SUMO_BIN" -p "$PORT"
