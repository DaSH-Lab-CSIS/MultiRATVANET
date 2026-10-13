#!/bin/bash
# Build script with detailed logging

cd "$(dirname "$0")" || exit 1

echo "=========================================="
echo "MultiRATVANET Framework Build"
echo "=========================================="
echo ""
echo "Compiler: $(g++ --version | head -1)"
echo "Make: $(make --version | head -1)"
echo ""

echo "Cleaning..."
make clean

echo ""
echo "Building with 4 parallel jobs..."
make -j4

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "✓ BUILD SUCCESSFUL!"
    echo "=========================================="
    echo ""
    ls -lh out/libmultiratvanet.dll
else
    echo ""
    echo "=========================================="
    echo "✗ BUILD FAILED (Exit code: $EXIT_CODE)"
    echo "=========================================="
    exit $EXIT_CODE
fi
