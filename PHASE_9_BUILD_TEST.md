# Phase 9 — Build Test & Verification

**Status:** READY TO EXECUTE  
**Estimated Time:** 5-10 minutes  
**Prerequisites:** Phase 8 complete (Makefiles generated)

---

## Quick Start

### Build Framework

**Option A: Windows (Recommended)**
```batch
cd MultiRATVANET
.\tools\build.bat
```

**Option B: Linux/macOS**
```bash
cd MultiRATVANET
./tools/build.sh
```

**Option C: Direct Make**
```bash
cd MultiRATVANET/framework
mingw32-make        # Windows
make                # Linux/macOS
```

---

## What to Expect

### Success Output
```
Compiling src/multirat/apps/V2vBeaconApp.cc...
Compiling src/multirat/manager/MultiRatAppManager.cc...
Compiling src/multirat/manager/RatStatsCollector.cc...
Compiling src/multirat/monitor/RatCoverageMonitor.cc...
Compiling src/multirat/policies/RatPolicyFactory.cc...
Linking out/libmultiratvanet.dll...
✓ Build successful: out/libmultiratvanet.dll
```

### What Gets Built
```
framework/out/
├── libmultiratvanet.dll           (main library)
├── apps/
│   └── V2vBeaconApp.o
├── manager/
│   ├── MultiRatAppManager.o
│   └── RatStatsCollector.o
└── monitor/
    └── RatCoverageMonitor.o
```

---

## Troubleshooting

### Issue: "g++: command not found"
```
Solution: Install MinGW or GCC
  Windows: Download MinGW from mingw-w64.org
  Linux: apt-get install build-essential
  macOS: xcode-select --install
```

### Issue: "cannot find -linet"
```
Solution: Verify frameworks are compiled
  cd ../inet-4.2.2-src/inet4 && make
  cd ../veins-5.2/veins-veins-5.2 && make
  cd ../Simu5G-1.1.0/Simu5G-1.1.0 && make
```

### Issue: Path errors or include not found
```
Solution: Check GNUmakefile framework paths
  Edit: framework/GNUmakefile
  Verify: INET_PATH, VEINS_PATH, SIMU5G_PATH point to correct locations
  Try: mingw32-make clean && mingw32-make
```

---

## Verification Steps

After build completes:

```bash
# 1. Check output file exists
ls -la framework/out/libmultiratvanet.*

# 2. Check size is reasonable (> 500 KB expected)
du -h framework/out/

# 3. Check for compiler warnings (expected some)
# 4. Look for linker errors (none should appear)
```

---

## Next Step After Success

**If build succeeds:**
```bash
# Proceed to Phase 10: First Simulation
./tools/run.sh Highway_CoveragePriority --sim-time-limit=70s
```

**If build fails:**
1. Read full error message
2. Check GNUmakefile paths
3. Verify frameworks compiled
4. See TROUBLESHOOTING.md in docs/

---

## Build System Debug

If you need more details:

```bash
# Verbose build (shows all commands)
mingw32-make V=1

# Clean and rebuild
mingw32-make clean
mingw32-make

# Show make variables
mingw32-make -p | grep -E "^(INET|VEINS|SIMU5G|SOURCES)"
```

---

## Expected Build Time

| Platform | Time | Factors |
|----------|------|---------|
| Windows (MinGW) | 2-5 min | -jN parallelization helps |
| Linux (GCC) | 1-3 min | Depends on disk speed |
| macOS (Clang) | 2-4 min | Framework linking is slowest part |

**First build may take longer due to initial compilation.**  
**Incremental builds are much faster (seconds).**

---

**Ready? → Run: `.\tools\build.bat` (Windows) or `./tools/build.sh` (Linux/macOS)**

See [PHASE_8_COMPLETE.md](PHASE_8_COMPLETE.md) for build system details.
