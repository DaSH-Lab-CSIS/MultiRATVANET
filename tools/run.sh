#!/bin/bash
# MultiRATVANET Run Script for Linux/macOS
# Usage: ./run.sh <CONFIG_NAME> [--sim-time-limit=XXXs] [--analyze]

set -e

CONFIG=$1
SIM_TIME="100s"
SUMO_PORT=9998
DO_ANALYZE=false

if [[ -z "$CONFIG" ]]; then
    echo "Usage: ./run.sh <CONFIG_NAME> [--sim-time-limit=XXXs] [--analyze]"
    echo ""
    echo "Available configs:"
    echo "  Highway_CoveragePriority, Highway_Ensemble, Highway_ML"
    echo "  UrbanGrid_Base, UrbanGrid_Ensemble, UrbanGrid_ML"
    echo "  ElectronicCity_Base, ElectronicCity_Ensemble, ElectronicCity_ML"
    echo ""
    exit 1
fi

# Parse additional arguments
shift
while [[ $# -gt 0 ]]; do
    case $1 in
        --sim-time-limit=*)
            SIM_TIME="${1#*=}"
            ;;
        --analyze)
            DO_ANALYZE=true
            ;;
    esac
    shift
done

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RESULTS_DIR="${RESULTS_ROOT:-$ROOT_DIR/results}/${CONFIG}_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RESULTS_DIR"

echo ""
echo "=== MultiRATVANET Simulation Launcher ==="
echo "Configuration: $CONFIG"
echo "Simulation time: $SIM_TIME"
echo "Results dir: $RESULTS_DIR"
echo ""

# Save config snapshot
cp "$ROOT_DIR/simulations/omnetpp.ini" "$RESULTS_DIR/run-settings.ini"

# Run simulation
cd "$ROOT_DIR"
"$ROOT_DIR/framework/out/clang-release/framework" \
    "$ROOT_DIR/simulations/omnetpp.ini" \
    -c "$CONFIG" \
    -u Cmdenv \
    -n "simulations/networks:framework/src/multirat/_ned:${INET_DIR:-/home/vnet/vehicular-sim/inet-4.6.0}/src:${VEINS_DIR:-/home/vnet/vehicular-sim/veins-5.3.1}/src/veins:${VEINS_DIR:-/home/vnet/vehicular-sim/veins-5.3.1}/subprojects/veins_inet/src/veins_inet:${SIMU5G_DIR:-/home/vnet/vehicular-sim/simu5g-1.7.0}/src:${SIMU5G_DIR:-/home/vnet/vehicular-sim/simu5g-1.7.0}/simulations" \
    --sim-time-limit="$SIM_TIME" \
    ${RESULTS_ROOT:+--result-dir="$RESULTS_DIR"} \
    -r 0

echo ""
echo "✓ Simulation complete"
echo "Results: $RESULTS_DIR"

# Analyze if requested
if [[ "$DO_ANALYZE" == true ]]; then
    echo ""
    echo "Running analysis..."
    python3 "$ROOT_DIR/tools/analysis/export-results.py" "$RESULTS_DIR"
fi
