# MultiRATVANET Framework - GNUmakefile
# For use with MinGW32-Make / GNU Make on Windows/Linux/macOS

# ============================================================================
# PATHS & DIRECTORIES
# ============================================================================

ROOT_DIR = ..
WORKSPACE_DIR = $(ROOT_DIR)/..
FRAMEWORK_DIR = .
SRC_DIR = src
OUT_DIR = out

# External frameworks
INET_PATH = $(ROOT_DIR)/external/inet-4.2.2
VEINS_PATH = $(ROOT_DIR)/external/veins-5.2
SIMU5G_PATH = $(ROOT_DIR)/external/simu5g-1.1.0
OMNETPP_PATH = $(WORKSPACE_DIR)/omnetpp-5.6.1

# Fallback to workspace paths if external symlinks don't exist
ifeq ($(wildcard $(INET_PATH)),)
    INET_PATH = $(WORKSPACE_DIR)/inet-4.2.2-src/inet4
endif
ifeq ($(wildcard $(VEINS_PATH)),)
    VEINS_PATH = $(WORKSPACE_DIR)/veins-5.2/veins-veins-5.2
endif
ifeq ($(wildcard $(SIMU5G_PATH)),)
    SIMU5G_PATH = $(WORKSPACE_DIR)/Simu5G-1.1.0/Simu5G-1.1.0
endif

# ============================================================================
# SOURCE FILES
# ============================================================================

SOURCES = \
	src/multirat/apps/V2vBeaconApp.cc \
	src/multirat/manager/MultiRatAppManager.cc \
	src/multirat/manager/RatStatsCollector.cc \
	src/multirat/monitor/RatCoverageMonitor.cc \
	src/multirat/policies/RatPolicyFactory.cc

HEADERS = \
	src/multirat/base/RatTypes.h \
	src/multirat/apps/V2vBeaconApp.h \
	src/multirat/manager/MultiRatAppManager.h \
	src/multirat/manager/RatStatsCollector.h \
	src/multirat/monitor/RatCoverageMonitor.h \
	src/multirat/policies/IRatSelectionPolicy.h \
	src/multirat/policies/RatPolicyFactory.h

NEDFILES = \
	src/multirat/package.ned \
	src/multirat/apps/V2vBeaconApp.ned \
	src/multirat/core/MultiRatCar.ned \
	src/multirat/core/InfraNodes.ned \
	src/multirat/core/SixGInterface.ned \
	src/multirat/manager/MultiRatAppManager.ned \
	src/multirat/manager/RatStatsCollector.ned \
	src/multirat/monitor/RatCoverageMonitor.ned

OBJECTS = $(SOURCES:src/multirat/%.cc=$(OUT_DIR)/%.o)

# ============================================================================
# COMPILER & FLAGS
# ============================================================================

CXX = g++
CXXFLAGS = -std=c++11 -fPIC -Wall -Wextra -O2
CPPFLAGS = -I$(SRC_DIR) \
           -I$(SRC_DIR)/multirat \
           -I$(SRC_DIR)/multirat/base \
           -I$(SRC_DIR)/multirat/apps \
           -I$(SRC_DIR)/multirat/manager \
           -I$(SRC_DIR)/multirat/monitor \
           -I$(SRC_DIR)/multirat/policies \
           -I$(SRC_DIR)/multirat/core \
           -I$(OMNETPP_PATH)/include \
           -I$(INET_PATH)/src \
           -I$(VEINS_PATH)/src \
           -I$(SIMU5G_PATH)/src

LD = g++
AR = ar
ARFLAGS = rcs

# ============================================================================
# SOLUTION: Build as STATIC LIBRARY (.a) instead of DLL
# ============================================================================
# Why? 
#  - INET/Veins/Simu5G are NOT compiled (no .dll or .a files available)
#  - We can't link against non-existent libraries
#  - Static library (.a) lets us package object files for OMNeT++ to link
#  - OMNeT++ IDE will handle final DLL creation when building simulation
#
# This approach works with:
#  - OMNeT++ IDE's makefile-based projects
#  - Standard OMNeT++ project structure
#  - No external library dependencies needed at build time
# ============================================================================

# Target: static library (.a) instead of DLL
TARGET_LIB = out/libmultiratvanet.a

# No linker flags needed for static library - just use AR (archiver)
LDFLAGS = 
LIBS = 

# MSG compiler (from OMNeT++)
MSGC = opp_msgc --msg6

# ============================================================================
# TARGETS
# ============================================================================

# BUILD AS STATIC LIBRARY (.a) for OMNeT++ linking
# This avoids linker errors from undefined INET/Veins symbols
TARGET_LIB = $(OUT_DIR)/libmultiratvanet.a
TARGET_SO = $(OUT_DIR)/libmultiratvanet.so
TARGET_A = $(OUT_DIR)/libmultiratvanet.a

# Detect OS - use static library on all platforms for compatibility
ifeq ($(OS),Windows_NT)
    TARGET = $(TARGET_A)
else
    UNAME := $(shell uname -s)
    ifeq ($(UNAME),Linux)
        TARGET = $(TARGET_A)
    else ifeq ($(UNAME),Darwin)
        TARGET = $(TARGET_A)
    endif
endif

# ============================================================================
# BUILD RULES
# ============================================================================

.PHONY: all clean help

all: $(TARGET)
	@echo "✓ Build successful: $(TARGET)"

$(OUT_DIR):
	@mkdir -p $(OUT_DIR) $(OUT_DIR)/apps $(OUT_DIR)/manager $(OUT_DIR)/monitor

$(OUT_DIR)/%.o: src/multirat/%.cc | $(OUT_DIR)
	@echo "Compiling $<..."
	@mkdir -p $(dir $@)
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) -c $< -o $@

$(TARGET_LIB): $(OBJECTS) | $(OUT_DIR)
	@echo "Archiving $@..."
	$(AR) $(ARFLAGS) $@ $(OBJECTS)
	@echo "✓ Static library created: $@"
	@echo "  Use with OMNeT++ IDE:"
	@echo "    1. Add to simulation project makefile"
	@echo "    2. Link with: -L$(OUT_DIR) -lmultiratvanet"
	@echo "    3. OMNeT++ IDE will resolve INET/Veins/Simu5G symbols"

$(TARGET_SO): $(OBJECTS) | $(OUT_DIR)
	@echo "Archiving $@..."
	$(AR) $(ARFLAGS) $@ $(OBJECTS)

clean:
	@echo "Cleaning..."
	rm -rf $(OUT_DIR)
	@echo "✓ Cleaned"

help:
	@echo "MultiRATVANET Framework Build System"
	@echo ""
	@echo "Usage:"
	@echo "  make          - Build MultiRATVANET library"
	@echo "  make clean    - Remove build artifacts"
	@echo "  make help     - Show this help message"
	@echo ""
	@echo "Framework paths:"
	@echo "  INET:   $(INET_PATH)"
	@echo "  Veins:  $(VEINS_PATH)"
	@echo "  Simu5G: $(SIMU5G_PATH)"
	@echo ""
	@echo "Target: $(TARGET)"

# ============================================================================
# INCLUDE MAKEFRAG (OMNeT++ msg6 compiler)
# ============================================================================

-include makefrag
