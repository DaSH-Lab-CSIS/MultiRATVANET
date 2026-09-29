#!/bin/bash
# MultiRATVANET Build Script for Linux/macOS
# Usage: ./build.sh [--test] [--clean]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
OMNETPP_BIN="${ROOT_DIR}/external/omnetpp-5.6.1/bin"
INET_DIR="${ROOT_DIR}/external/inet-4.2.2"
VEINS_DIR="${ROOT_DIR}/external/veins-5.2"
SIMU5G_DIR="${ROOT_DIR}/external/simu5g-1.1.0"

export PATH="${OMNETPP_BIN}:${PATH}"

echo ""
echo "=== Building MultiRATVANET Framework ==="
echo "Root: $ROOT_DIR"
echo ""

cd "$ROOT_DIR/framework"

# Handle --clean flag
if [[ "$1" == "--clean" ]]; then
    echo "Cleaning..."
    rm -rf out Makefile Makefile.inc
    echo "✓ Cleaned"
    exit 0
fi

# Check for opp_makemake
if ! command -v opp_makemake &> /dev/null; then
    echo "ERROR: opp_makemake not found!"
    echo "Please verify OMNeT++ path: $OMNETPP_BIN"
    exit 1
fi

echo "Generating Makefile..."
opp_makemake -f --deep -O out \
    -I "$INET_DIR/src" \
    -I "$VEINS_DIR/src" \
    -I "$SIMU5G_DIR/src" \
    -L "$INET_DIR/src" \
    -L "$VEINS_DIR/src" \
    -L "$SIMU5G_DIR/src"

echo "Compiling (parallel build)..."
make -j$(nproc 2>/dev/null || echo 4)

if [[ -f "out/libmultiratvanet.so" ]] || [[ -f "out/libmultiratvanet.a" ]]; then
    echo ""
    echo "✓ Build successful"
    ls -lh out/libmultiratvanet.*
else
    echo "ERROR: Build completed but output not found!"
    exit 1
fi

# Run tests if --test flag
if [[ "$1" == "--test" ]]; then
    echo ""
    echo "Running unit tests..."
    cd "$ROOT_DIR/tests/unit"
    make -j4
fi
