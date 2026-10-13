#!/usr/bin/env bash
# ============================================================================
# MultiRATVANET - launch the simulation in the OMNeT++ graphical runtime (Qtenv)
# WITHOUT the Eclipse IDE. Gives the same "OMNeT++ simulation environment"
# window but avoids the IDE launch delegate.
#
# Start the SUMO launch daemon first, then this:
#   ./tools/sumo-launchd.sh 9998 sumo-gui.exe   # in one shell
#   ./tools/run-gui.sh                          # opens Qtenv; pick a config
#   ./tools/run-gui.sh MultiRatHighway_Base     # opens Qtenv on that config
#
# Metrics recording (.sca/.vec) is controlled by simulations/omnetpp.ini.
# ============================================================================
set -e

PROJ_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # repo root
WS_DIR="$(cd "$PROJ_DIR/.." && pwd)"                          # workspace root

# OMNeT++ (the full install with opp_run + Qt runtime lives in the workspace).
OMNETPP_ROOT="$WS_DIR/omnetpp-5.6.1"

# NOTE: the external/ dependency copies trigger an INET module-registry
# corruption at runtime (identical DLLs, but loading them from external/ crashes
# the WiFi MAC construction). The byte-identical workspace builds load cleanly.
INET="$WS_DIR/inet-4.2.2-src/inet4"
VEINS="$WS_DIR/veins-5.2/veins-veins-5.2"
VEINS_INET="$VEINS/subprojects/veins_inet"
SIMU5G="$WS_DIR/Simu5G-1.1.0/Simu5G-1.1.0"
FRAMEWORK="$PROJ_DIR/framework"

if [ ! -x "$OMNETPP_ROOT/bin/opp_run" ] && [ ! -f "$OMNETPP_ROOT/bin/opp_run" ]; then
    echo "ERROR: opp_run not found under $OMNETPP_ROOT/bin" >&2
    exit 1
fi

# Locate the built framework shared library and its directory. opp_run -l takes
# the base name ("multiratvanet"); it prepends "lib" and appends .dll/.so.
SELF_DIR=""
for d in "$FRAMEWORK/out" "$FRAMEWORK"/out/*/; do
    if [ -f "${d%/}/libmultiratvanet.dll" ] || [ -f "${d%/}/libmultiratvanet.so" ]; then
        SELF_DIR="${d%/}"; break
    fi
done
if [ -z "$SELF_DIR" ]; then
    echo "ERROR: built shared library (libmultiratvanet.dll/.so) not found under" >&2
    echo "       $FRAMEWORK/out" >&2
    echo "       Build a SHARED library first, e.g.:" >&2
    echo "         cd framework && opp_makemake -f --deep --make-so -O out ... && make" >&2
    exit 1
fi

export OMNETPP_ROOT
# DLL search path: dependency libraries AND the Qt/Qtenv runtime DLLs.
export PATH="$OMNETPP_ROOT/bin:/mingw64/bin:/usr/bin:\
$SELF_DIR:\
$INET/src:$VEINS/src:$VEINS_INET/src:$SIMU5G/src:$PATH"

# opp_run is a native Windows binary and its path parser splits on ':', so
# drive-letter paths (D:/...) break. Use relative NED paths (cwd = PROJ_DIR).
# The framework uses a flat 'multiratvanet' package split across subfolders, so
# each subfolder is its own NED source root; simulations NED roots at networks/.
NEDPATH="framework/src/multirat/apps;framework/src/multirat/core;\
framework/src/multirat/manager;framework/src/multirat/monitor;\
simulations/networks;\
../inet-4.2.2-src/inet4/src;\
../Simu5G-1.1.0/Simu5G-1.1.0/src;\
../Simu5G-1.1.0/Simu5G-1.1.0/simulations;\
../veins-5.2/veins-veins-5.2/src/veins;\
../veins-5.2/veins-veins-5.2/subprojects/veins_inet/src/veins_inet"

cd "$PROJ_DIR"

# First positional arg is the config name (unless it starts with '-').
if [ $# -gt 0 ] && [ "${1#-}" = "$1" ]; then
    CONFIG="$1"; shift
    set -- -c "$CONFIG" "$@"
fi

# Once Qt initialises it calls SetDllDirectory(), which stops Windows from using
# PATH to resolve the dependencies of dynamically loaded model libraries. So,
# unlike a Cmdenv script, load every library by ABSOLUTE (native Windows) path.
L_INET="$(cygpath -w "$INET/src/INET")"
L_VEINS="$(cygpath -w "$VEINS/src/veins")"
L_VEINS_INET="$(cygpath -w "$VEINS_INET/src/veins_inet")"
L_SIMU5G="$(cygpath -w "$SIMU5G/src/simu5g")"
L_SELF="$(cygpath -w "$SELF_DIR/multiratvanet")"
IMG="$(cygpath -w "$INET/images");$(cygpath -w "$SIMU5G/images");$(cygpath -w "$VEINS/images")"

# -u Qtenv opens the graphical simulation environment. The image-path lets Qtenv
# find the module icons/backgrounds used by INET/Simu5G.
opp_run \
  -l "$L_INET" \
  -l "$L_VEINS" \
  -l "$L_VEINS_INET" \
  -l "$L_SIMU5G" \
  -l "$L_SELF" \
  -n "$NEDPATH" \
  --image-path="$IMG" \
  -u Qtenv "$@" simulations/omnetpp.ini
