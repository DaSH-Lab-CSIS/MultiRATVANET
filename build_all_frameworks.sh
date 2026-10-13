#!/bin/bash
# ============================================================================
# MultiRATVANET Framework Build Script
# Automatically builds INET, Veins, Simu5G, and MultiRATVANET in sequence
# ============================================================================

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Paths
WORKSPACE="/d/Desktop_PCBackup/Mari-Per/PhD_Research/Federated_Learning/Course_Work/Work@2026/Simulation"
OMNETPP_ROOT="$WORKSPACE/omnetpp-5.6.1"
# The framework links against the compiled copies under external/.
INET_DIR="$WORKSPACE/MultiRATVANET/external/inet-4.2.2"
VEINS_DIR="$WORKSPACE/MultiRATVANET/external/veins-5.2"
VEINS_INET_DIR="$VEINS_DIR/subprojects/veins_inet"
SIMU5G_DIR="$WORKSPACE/MultiRATVANET/external/simu5g-1.1.0"
MULTIRAT_DIR="$WORKSPACE/MultiRATVANET/framework"

# ============================================================================
# Setup
# ============================================================================

echo -e "${BLUE}"
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║    MultiRATVANET Framework Build System                       ║"
echo "║    Building: INET → Veins → Simu5G → MultiRATVANET          ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Set OMNeT++ environment
export OMNETPP_ROOT="$OMNETPP_ROOT"
export PATH="$OMNETPP_ROOT/bin:$PATH"

echo -e "${BLUE}[SETUP]${NC} Setting OMNeT++ environment..."
echo "  OMNETPP_ROOT: $OMNETPP_ROOT"
echo "  PATH includes: $OMNETPP_ROOT/bin"

# Verify OMNeT++ is accessible
if ! command -v opp_configfilepath &> /dev/null; then
    echo -e "${RED}[ERROR] OMNeT++ not found in PATH${NC}"
    exit 1
fi

echo -e "${GREEN}✓ OMNeT++ environment verified${NC}"
echo ""

# ============================================================================
# Build Functions
# ============================================================================

build_framework() {
    local name=$1
    local dir=$2
    local extra_config=$3
    
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}[BUILD] Building $name...${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    if [ ! -d "$dir" ]; then
        echo -e "${RED}[ERROR] Directory not found: $dir${NC}"
        return 1
    fi
    
    cd "$dir"
    
    # Configure
    echo -e "${BLUE}[1/3] Configuring $name...${NC}"
    if [ -n "$extra_config" ]; then
        ./configure $extra_config 2>&1 | head -20
    else
        ./configure 2>&1 | head -20
    fi
    
    echo -e "${GREEN}✓ Configuration complete${NC}"
    echo ""
    
    # Clean
    echo -e "${BLUE}[2/3] Cleaning $name...${NC}"
    make clean > /dev/null 2>&1 || true
    echo -e "${GREEN}✓ Clean complete${NC}"
    echo ""
    
    # Build
    echo -e "${BLUE}[3/3] Compiling $name (this may take a few minutes)...${NC}"
    start_time=$(date +%s)
    
    if make -j4 2>&1 | tee build_${name}.log; then
        end_time=$(date +%s)
        duration=$((end_time - start_time))
        
        echo -e "${GREEN}"
        echo "✓ $name build successful! (${duration}s)"
        echo -e "${NC}"
        return 0
    else
        echo -e "${RED}"
        echo "✗ $name build FAILED!"
        echo "Check: $dir/build_${name}.log"
        echo -e "${NC}"
        return 1
    fi
}

verify_dll() {
    local name=$1
    local dll_path=$2
    
    if [ -f "$dll_path" ]; then
        size=$(ls -lh "$dll_path" | awk '{print $5}')
        echo -e "${GREEN}✓ $name: $dll_path ($size)${NC}"
        return 0
    else
        echo -e "${RED}✗ $name DLL not found: $dll_path${NC}"
        return 1
    fi
}

# ============================================================================
# Main Build Sequence
# ============================================================================

# Track success
FAILED=0

# Dependency frameworks are prebuilt (verified below). This script does NOT
# clean/rebuild them, to avoid wiping existing INET/Veins/Simu5G binaries.
echo -e "${BLUE}[INFO] Skipping INET/Veins/Simu5G rebuild (using prebuilt libs).${NC}"
echo ""

# ============================================================================
# Verification
# ============================================================================

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}[VERIFY] Checking DLL files...${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

DLL_FAILED=0

verify_dll "INET" "$INET_DIR/src/libINET.dll" || DLL_FAILED=$((DLL_FAILED + 1))
verify_dll "Veins" "$VEINS_DIR/src/libveins.dll" || DLL_FAILED=$((DLL_FAILED + 1))
verify_dll "veins_inet" "$VEINS_INET_DIR/src/libveins_inet.dll" || DLL_FAILED=$((DLL_FAILED + 1))
verify_dll "Simu5G" "$SIMU5G_DIR/src/libsimu5g.dll" || DLL_FAILED=$((DLL_FAILED + 1))

echo ""

# ============================================================================
# Build MultiRATVANET
# ============================================================================

if [ $FAILED -eq 0 ] && [ $DLL_FAILED -eq 0 ]; then
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}[BUILD] Building MultiRATVANET Framework...${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    cd "$MULTIRAT_DIR"
    
    echo -e "${BLUE}[1/2] Preparing (keeping prebuilt libs)...${NC}"
    true  # no clean: build-so.sh regenerates the Makefile and relinks
    echo -e "${GREEN}✓ Clean complete${NC}"
    echo ""
    
    echo -e "${BLUE}[2/2] Building MultiRATVANET DLL...${NC}"
    if bash "$WORKSPACE/MultiRATVANET/tools/build-so.sh" release 2>&1 | tee build_multiratvanet.log; then
        echo -e "${GREEN}"
        echo "✓ MultiRATVANET build successful!"
        echo -e "${NC}"
        
        if [ -f "$MULTIRAT_DIR/out/libmultiratvanet.dll" ]; then
            size=$(ls -lh "$MULTIRAT_DIR/out/libmultiratvanet.dll" | awk '{print $5}')
            echo -e "${GREEN}✓ libmultiratvanet.dll created ($size)${NC}"
        fi
    else
        echo -e "${RED}✗ MultiRATVANET build FAILED${NC}"
        FAILED=$((FAILED + 1))
    fi
else
    echo -e "${RED}"
    echo "✗ Skipping MultiRATVANET build due to framework errors"
    echo -e "${NC}"
    FAILED=$((FAILED + 1))
fi

echo ""

# ============================================================================
# Summary
# ============================================================================

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}"
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║           ✓ ALL BUILDS SUCCESSFUL!                            ║"
    echo "║                                                                ║"
    echo "║  Ready to launch OMNeT++ and run simulations!                 ║"
    echo "║                                                                ║"
    echo "║  Next steps:                                                   ║"
    echo "║    1. Launch OMNeT++: omnetpp.cmd                             ║"
    echo "║    2. Open simulations project                                ║"
    echo "║    3. Build and run simulations                               ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    exit 0
else
    echo -e "${RED}"
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║           ✗ BUILD FAILED                                       ║"
    echo "║                                                                ║"
    echo "║  Check build logs:                                             ║"
    echo "║    - $INET_DIR/build_INET.log"
    echo "║    - $VEINS_DIR/build_Veins.log"
    echo "║    - $SIMU5G_DIR/build_Simu5G.log"
    echo "║    - $MULTIRAT_DIR/build_multiratvanet.log"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    exit 1
fi
