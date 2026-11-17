#!/bin/bash
# MultiRATVANET Run Script for Linux/macOS
# Usage: ./run.sh <CONFIG_NAME> [--sim-time-limit=XXXs] [--run=N] [--<ini-key>=<value> ...]
#
#   --sim-time-limit=T   simulated time; default: the config's own sim-time-limit in omnetpp.ini
#   --run=FILTER         which runs of the config (OMNeT++ -r, e.g. 0 or 0..3); default: all of
#                        them (one, except for parameter studies such as EnsembleSweep)
#   --<ini-key>=<value>  any other option is passed to the simulation as a parameter override
#
# Results go to $RESULTS_ROOT/<CONFIG>_<timestamp>/ (RESULTS_ROOT defaults to <repo>/results).
# Needs veins_launchd listening on the port in omnetpp.ini (9999); tools/sumo-launchd.sh starts one.

set -e

CONFIG=$1
SIM_TIME=""
RUN_FILTER=""
EXTRA_ARGS=()   # any other --option=value is passed straight to the simulation (parameter overrides)

if [[ -z "$CONFIG" ]]; then
    echo "Usage: ./run.sh <CONFIG_NAME> [--sim-time-limit=XXXs] [--run=N] [--<ini-key>=<value> ...]"
    echo ""
    echo "Available configs (see simulations/omnetpp.ini):"
    echo "  Highway: CoveragePriority, Sinr, LatencyQos, Load, Ml, Ensemble, EnsembleSweep,"
    echo "           DsrcNrHandover, V2V, CV2X"
    echo "  UrbanGrid_CoveragePriority, UrbanGrid_Ensemble, UrbanGrid_ML"
    echo "  ElectronicCity_CoveragePriority, ElectronicCity_Ensemble, ElectronicCity_ML"
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
        --run=*)
            RUN_FILTER="${1#*=}"
            ;;
        *)
            EXTRA_ARGS+=("$1")
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
echo "Simulation time: ${SIM_TIME:-as set in omnetpp.ini}"
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
    ${SIM_TIME:+--sim-time-limit="$SIM_TIME"} \
    --result-dir="$RESULTS_DIR" \
    "${EXTRA_ARGS[@]}" \
    ${RUN_FILTER:+-r "$RUN_FILTER"}

echo ""
echo "✓ Simulation complete"
echo "Results: $RESULTS_DIR"
