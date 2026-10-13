#!/bin/bash
# Build script for MultiRATVANET Framework
# Run this from inside MSYS2 MinGW shell

set -e  # Exit on error

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
MULTIRAT_DIR="$SCRIPT_DIR/.."
FRAMEWORK_DIR="$MULTIRAT_DIR/framework"

echo ""
echo "=========================================="
echo "  MultiRATVANET Framework Build"
echo "=========================================="
echo ""
echo "Framework: $FRAMEWORK_DIR"
echo ""

cd "$FRAMEWORK_DIR"

echo "Running: make -j4"
echo ""

if make -j4; then
    echo ""
    echo "=========================================="
    echo "  BUILD SUCCESSFUL!"
    echo "=========================================="
    echo ""
    if [ -f "out/libmultiratvanet.dll" ]; then
        echo "✓ Output: $(ls -lh out/libmultiratvanet.dll)"
    else
        echo "Looking for output files..."
        find out -type f 2>/dev/null || echo "No output files found"
    fi
else
    echo ""
    echo "=========================================="
    echo "  BUILD FAILED"
    echo "=========================================="
    exit 1
fi
