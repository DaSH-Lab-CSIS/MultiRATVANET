# Getting Started with MultiRATVANET

This guide will help you set up MultiRATVANET and run your first simulation.

## Prerequisites

### Required
- **OMNeT++ 5.6.1** (compiled & bin/ on PATH)
- **INET 4.2.2** (compiled)
- **Veins 5.2** (compiled, with veins_inet)
- **Simu5G 1.1.0** (compiled)
- **SUMO 1.24+** (on PATH)
- **MinGW** (for Windows builds) or **GCC** (for Linux)

### Optional
- **Python 3.8+** (for analysis tools)
- **pandas, matplotlib, numpy** (for plotting)
- **Docker** (for containerized builds)

## Installation

### 1. Verify Framework Paths

The build system expects frameworks in `external/`:

```bash
cd MultiRATVANET
ls -la external/
# Should show symlinks to:
# - omnetpp-5.6.1
# - inet-4.2.2
# - veins-5.2
# - simu5g-1.1.0
```

If symlinks are missing, create them:

**Linux/macOS:**
```bash
cd external
ln -s ../../omnetpp-5.6.1 .
ln -s ../../inet-4.2.2-src/inet4 inet-4.2.2
ln -s ../../veins-5.2/veins-veins-5.2 veins-5.2
ln -s ../../Simu5G-1.1.0/Simu5G-1.1.0 simu5g-1.1.0
```

**Windows (PowerShell as Admin):**
```powershell
cd external
New-Item -ItemType SymbolicLink -Path "omnetpp-5.6.1" -Target "../../omnetpp-5.6.1"
New-Item -ItemType SymbolicLink -Path "inet-4.2.2" -Target "../../inet-4.2.2-src/inet4"
New-Item -ItemType SymbolicLink -Path "veins-5.2" -Target "../../veins-5.2/veins-veins-5.2"
New-Item -ItemType SymbolicLink -Path "simu5g-1.1.0" -Target "../../Simu5G-1.1.0/Simu5G-1.1.0"
```

### 2. Verify OMNeT++ on PATH

Test that OMNeT++ tools are accessible:

```bash
which opp_makemake    # Linux/macOS
where opp_makemake    # Windows

# Output should show path to OMNeT++ bin directory
```

If not found, add OMNeT++ to PATH:

**Linux/macOS:**
```bash
export PATH=$PATH:/path/to/omnetpp-5.6.1/bin
```

**Windows:**
- Set PATH environment variable to include omnetpp-5.6.1\bin

### 3. Build MultiRATVANET

```bash
cd MultiRATVANET

# Windows
.\tools\build.bat

# Linux/macOS
./tools/build.sh
```

Expected output:
```
=== Building MultiRATVANET Framework ===
...
Compiling (parallel build)...
...
✓ Build successful
Output: out/libmultiratvanet.dll  (Windows)
        out/libmultiratvanet.so   (Linux)
```

### 4. Run First Simulation

```bash
# Windows
.\tools\run.bat Highway_CoveragePriority 70s

# Linux/macOS
./tools/run.sh Highway_CoveragePriority --sim-time-limit=70s
```

Expected output:
```
=== MultiRATVANET Simulation Launcher ===
Configuration: Highway_CoveragePriority
Simulation time: 70s
Results dir: results/Highway_CoveragePriority_20260929_143022/

[OMNeT++ simulation runs...]

✓ Simulation complete
Results: results/Highway_CoveragePriority_20260929_143022/
```

## First Results

After the simulation completes, check the results:

```bash
ls -la results/Highway_CoveragePriority_*/

# Should contain:
# - run-settings.ini        (config snapshot)
# - *.sca                   (statistics)
# - *.vec                   (time-series data)
# - analysis/               (if analysis was run)
```

## Verify Installation

Run a quick verification:

```bash
# Check build artifacts
ls -lh framework/out/

# Check simulation results
ls -la results/

# Verify Python tools (optional)
python -c "import pandas, matplotlib; print('✓ Analysis tools available')"
```

## Next Steps

1. **Read [ARCHITECTURE.md](ARCHITECTURE.md)** — Understand the system design
2. **Try different scenarios:**
   ```bash
   ./tools/run.sh UrbanGrid_Ensemble --sim-time-limit=120s
   ./tools/run.sh ElectronicCity_Base --sim-time-limit=200s
   ```
3. **Analyze results:**
   ```bash
   python tools/analysis/export-results.py results/Highway_*/
   python tools/analysis/plot-residency.py results/Highway_*/
   ```
4. **Follow tutorials in [tutorials/](tutorials/)** for advanced topics

## Troubleshooting

**Problem:** `opp_makemake: not found`
```
Solution: Add OMNeT++ bin/ to PATH (see step 2 above)
```

**Problem:** `cannot find INET library`
```
Solution: Verify INET 4.2.2 is compiled and inet-4.2.2 symlink exists in external/
Run: cd external/inet-4.2.2 && make
```

**Problem:** SUMO connection fails
```
Solution: Verify SUMO is on PATH: which sumo
          Ensure only ONE SUMO daemon runs on port 9998
```

**Problem:** Simulation doesn't produce output
```
Solution: Check results/ directory was created
          Check omnetpp.ini for [Config] section matching CONFIG name
          Enable vector/scalar recording (see config/omnetpp.ini)
```

For more help, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## System Requirements

| Component | Version | Size | Time to Compile |
|-----------|---------|------|-----------------|
| OMNeT++ | 5.6.1 | 500MB | 10-15 min |
| INET | 4.2.2 | 200MB | 20-30 min |
| Veins | 5.2 | 100MB | 10-15 min |
| Simu5G | 1.1.0 | 150MB | 15-20 min |
| SUMO | 1.24+ | 300MB | Precompiled |
| **MultiRATVANET** | **1.0** | **~1MB** | **2-5 min** |

---

**Ready? Let's build:** `./tools/build.sh`

For questions, see the [full documentation index](INDEX.md).
