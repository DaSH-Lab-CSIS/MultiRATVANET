# MultiRATVANET Framework - GNUmakefile
# For use with MinGW32-Make / GNU Make on Windows/Linux/macOS

# ============================================================================
# PATHS & DIRECTORIES
# ============================================================================

ROOT_DIR = ..
FRAMEWORK_DIR = .
SRC_DIR = src
OUT_DIR = out

# External frameworks
INET_PATH = $(ROOT_DIR)/external/inet-4.2.2
VEINS_PATH = $(ROOT_DIR)/external/veins-5.2
SIMU5G_PATH = $(ROOT_DIR)/external/simu5g-1.1.0

# Fallback to workspace paths if external symlinks don't exist
ifeq ($(wildcard $(INET_PATH)),)
    INET_PATH = $(ROOT_DIR)/inet-4.2.2-src/inet4
endif
ifeq ($(wildcard $(VEINS_PATH)),)
    VEINS_PATH = $(ROOT_DIR)/veins-5.2/veins-veins-5.2
endif
ifeq ($(wildcard $(SIMU5G_PATH)),)
    SIMU5G_PATH = $(ROOT_DIR)/Simu5G-1.1.0/Simu5G-1.1.0
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
           -I$(INET_PATH)/src \
           -I$(VEINS_PATH)/src \
           -I$(SIMU5G_PATH)/src

LD = g++
LDFLAGS = -shared -L$(OUT_DIR) \
          -L$(INET_PATH)/src \
          -L$(VEINS_PATH)/src \
          -L$(SIMU5G_PATH)/src
LIBS = -linet -lveins -lsimu5g -lm

# MSG compiler (from OMNeT++)
MSGC = opp_msgc --msg6

# ============================================================================
# TARGETS
# ============================================================================

TARGET_LIB = $(OUT_DIR)/libmultiratvanet.dll
TARGET_SO = $(OUT_DIR)/libmultiratvanet.so
TARGET_A = $(OUT_DIR)/libmultiratvanet.a

# Detect OS
ifeq ($(OS),Windows_NT)
    TARGET = $(TARGET_LIB)
else
    UNAME := $(shell uname -s)
    ifeq ($(UNAME),Linux)
        TARGET = $(TARGET_SO)
    else ifeq ($(UNAME),Darwin)
        TARGET = $(TARGET_SO)
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
	@echo "Linking $@..."
	$(LD) $(LDFLAGS) -o $@ $(OBJECTS) $(LIBS)

$(TARGET_SO): $(OBJECTS) | $(OUT_DIR)
	@echo "Linking $@..."
	$(LD) $(LDFLAGS) -o $@ $(OBJECTS) $(LIBS)

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
