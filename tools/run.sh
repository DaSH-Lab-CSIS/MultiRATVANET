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
RESULTS_DIR="$ROOT_DIR/results/${CONFIG}_$(date +%Y%m%d_%H%M%S)"
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
"$ROOT_DIR/framework/out/MultiRatVanet" \
    -c "$CONFIG" \
    -u Cmdenv \
    -n "simulations:framework/src" \
    --sim-time-limit="$SIM_TIME" \
    -r 0 \
    **.vector-recording=true \
    **.scalar-recording=true

echo ""
echo "✓ Simulation complete"
echo "Results: $RESULTS_DIR"

# Analyze if requested
if [[ "$DO_ANALYZE" == true ]]; then
    echo ""
    echo "Running analysis..."
    python3 "$ROOT_DIR/tools/analysis/export-results.py" "$RESULTS_DIR"
fi
