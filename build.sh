#!/bin/bash
# Build script for MultiRATVANET Framework
# This script must be run from within MSYS2 MinGW64 shell

cd "$(dirname "$0")/framework" || exit 1

echo "=================================="
echo "MultiRATVANET Framework Build"
echo "=================================="
echo ""
echo "Cleaning previous build..."
make clean

echo ""
echo "Building with 4 parallel jobs..."
make -j4

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Build successful!"
    echo "Output: $(pwd)/out/libmultiratvanet.dll"
else
    echo ""
    echo "✗ Build failed!"
    exit 1
fi
