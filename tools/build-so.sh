#!/usr/bin/env bash
# ============================================================================
# MultiRATVANET - build the framework as a SHARED library (libmultiratvanet.dll
# / .so) that opp_run (and tools/run-gui.sh) can load with -l.
#
# Unlike the static build in framework/GNUmakefile, this links against the
# compiled INET / Veins / veins_inet / Simu5G shared libraries under external/.
#
# Usage:
#   ./tools/build-so.sh [MODE]      MODE = release (default) | debug
#
# Output: framework/out/<toolchain>-<MODE>/libmultiratvanet.dll
# ============================================================================
set -e

MODE="${1:-release}"

PROJ_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # repo root
WS_DIR="$(cd "$PROJ_DIR/.." && pwd)"                          # workspace root
OMNETPP_ROOT="$WS_DIR/omnetpp-5.6.1"

# NOTE: link against the WORKSPACE dependency builds. The byte-identical copies
# under external/ cause an INET module-registry corruption when loaded at
# runtime, so run-gui.sh loads the workspace libs; build against the same set.
INET="$WS_DIR/inet-4.2.2-src/inet4"
VEINS="$WS_DIR/veins-5.2/veins-veins-5.2"
VEINS_INET="$VEINS/subprojects/veins_inet"
SIMU5G="$WS_DIR/Simu5G-1.1.0/Simu5G-1.1.0"
FRAMEWORK="$PROJ_DIR/framework"

export OMNETPP_ROOT
export PATH="$OMNETPP_ROOT/bin:$PATH"

if ! command -v opp_makemake >/dev/null 2>&1; then
    echo "ERROR: opp_makemake not found. Expected at $OMNETPP_ROOT/bin" >&2
    exit 1
fi

for lib in "$INET/src/libINET.dll" "$VEINS/src/libveins.dll" \
           "$VEINS_INET/src/libveins_inet.dll" "$SIMU5G/src/libsimu5g.dll"; do
    if [ ! -f "$lib" ]; then
        echo "ERROR: dependency not built: $lib" >&2
        echo "       Build INET/Veins/veins_inet/Simu5G (release) first." >&2
        exit 1
    fi
done

cd "$FRAMEWORK"

echo "=== Generating shared-library Makefile (opp_makemake --make-so) ==="
# -o multiratvanet  -> libmultiratvanet.<dll|so>
# --deep            -> compile every source under src/ recursively
# -I src, -I src/multirat let headers be included by sub-path prefix
#                      (e.g. "base/RatTypes.h", "policies/RatPolicyFactory.h").
# GNUmakefile is left untouched; we build the generated Makefile explicitly.
opp_makemake -f --deep --make-so -o multiratvanet -O out \
    -I"$FRAMEWORK/src" -I"$FRAMEWORK/src/multirat" \
    -I"$FRAMEWORK/src/multirat/base" -I"$FRAMEWORK/src/multirat/apps" \
    -I"$FRAMEWORK/src/multirat/core" -I"$FRAMEWORK/src/multirat/manager" \
    -I"$FRAMEWORK/src/multirat/monitor" -I"$FRAMEWORK/src/multirat/policies" \
    -I"$INET/src" -I"$VEINS/src" -I"$VEINS_INET/src" -I"$SIMU5G/src" \
    -L"$INET/src" -L"$VEINS/src" -L"$VEINS_INET/src" -L"$SIMU5G/src" \
    -lINET -lveins -lsimu5g
    # NOTE: libveins_inet is deliberately NOT linked. Our C++ uses no veins_inet
    # symbols, and it is the only GCC-built dependency (the rest, incl. our lib,
    # are clang) -- linking it mixed C++ RTTI and corrupted the module registry
    # at runtime. Its NED types are still provided at load time by run-gui.sh.

echo "=== Building (MODE=$MODE) ==="
make -f Makefile MODE="$MODE" -j"$(nproc 2>/dev/null || echo 4)"

echo ""
echo "=== Result ==="
ls -lh out/*/libmultiratvanet.* 2>/dev/null || {
    echo "ERROR: no shared library produced." >&2
    exit 1
}
