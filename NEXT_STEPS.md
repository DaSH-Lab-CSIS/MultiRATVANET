# MultiRATVANET — Next Steps

**Current Status:** Repository Structure Complete (Phase 1-7)  
**Commit:** dcd1ddb  
**Ready for:** Makefile Generation & Build Testing

---

## 🎯 Next 3 Steps (Recommended Order)

### Step 1: Create Framework Symlinks (5 minutes)

**Why:** The build scripts reference external frameworks via symlinks.

**On Windows (PowerShell as Admin):**
```powershell
cd external

# Create symlinks to frameworks
New-Item -ItemType SymbolicLink -Path "omnetpp-5.6.1" -Target "../../omnetpp-5.6.1" -Force
New-Item -ItemType SymbolicLink -Path "inet-4.2.2" -Target "../../inet-4.2.2-src/inet4" -Force
New-Item -ItemType SymbolicLink -Path "veins-5.2" -Target "../../veins-5.2/veins-veins-5.2" -Force
New-Item -ItemType SymbolicLink -Path "simu5g-1.1.0" -Target "../../Simu5G-1.1.0/Simu5G-1.1.0" -Force

# Verify
Get-ChildItem | Format-Table Name, Target
```

**On Linux/macOS:**
```bash
cd external

ln -s ../../omnetpp-5.6.1 .
ln -s ../../inet-4.2.2-src/inet4 inet-4.2.2
ln -s ../../veins-5.2/veins-veins-5.2 veins-5.2
ln -s ../../Simu5G-1.1.0/Simu5G-1.1.0 simu5g-1.1.0

ls -la
```

### Step 2: Generate Makefile (5 minutes)

**Why:** opp_makemake creates the build rules from makefrag.

**From MinGW/MSYS2 shell (Windows):**
```bash
cd framework

opp_makemake -f --deep -O out \
    -I ../external/inet-4.2.2/src \
    -I ../external/veins-5.2/src \
    -I ../external/simu5g-1.1.0/src \
    -L ../external/inet-4.2.2/src \
    -L ../external/veins-5.2/src \
    -L ../external/simu5g-1.1.0/src

# Verify
ls -la Makefile Makefile.inc
```

**On Linux/macOS:**
```bash
cd framework

opp_makemake -f --deep -O out \
    -I ../external/inet-4.2.2/src \
    -I ../external/veins-5.2/src \
    -I ../external/simu5g-1.1.0/src \
    -L ../external/inet-4.2.2/src \
    -L ../external/veins-5.2/src \
    -L ../external/simu5g-1.1.0/src

ls -la Makefile Makefile.inc
```

### Step 3: Test Build (2-5 minutes)

**Windows:**
```batch
cd ..
.\tools\build.bat

# Expected: "✓ Build successful: out/libmultiratvanet.dll"
```

**Linux/macOS:**
```bash
cd ..
./tools/build.sh

# Expected: "✓ Build successful" and libmultiratvanet.so
```

---

## ✅ After Successful Build

### Run First Simulation (10 minutes)

```bash
# Windows
.\tools\run.bat Highway_CoveragePriority 70s

# Linux/macOS
./tools/run.sh Highway_CoveragePriority --sim-time-limit=70s
```

**Expected output:**
```
=== MultiRATVANET Simulation Launcher ===
Configuration: Highway_CoveragePriority
Simulation time: 70s
Results dir: results/Highway_CoveragePriority_20260929_143022/

[... OMNeT++ simulation output ...]

✓ Simulation complete
Results: results/Highway_CoveragePriority_20260929_143022/
```

### Check Results

```bash
ls -la results/Highway_CoveragePriority_*/

# Should contain:
# - run-settings.ini      (config snapshot)
# - *.sca                 (statistics)
# - *.vec                 (vectors)
```

---

## 📋 Troubleshooting

### Issue: "opp_makemake: not found"

**Solution:**  
Add OMNeT++ bin/ to PATH:

**Windows (PowerShell):**
```powershell
$env:PATH += ";D:\path\to\omnetpp-5.6.1\bin"
```

**Linux/macOS:**
```bash
export PATH=$PATH:/path/to/omnetpp-5.6.1/bin
```

### Issue: "cannot find -linet"

**Solution:**  
Verify external symlinks exist:
```bash
cd external
ls -la inet-4.2.2 veins-5.2 simu5g-1.1.0

# Each should show → /path/to/framework
```

### Issue: Build starts but fails with "undefined reference"

**Solution:**  
Frameworks may not be compiled. Compile them:
```bash
cd ../inet-4.2.2 && make
cd ../veins-5.2 && make
cd ../Simu5G-1.1.0 && make
```

### Issue: Simulation fails with "Config not found"

**Solution:**  
Check simulations/omnetpp.ini has the config:
```bash
grep "\[Config Highway_CoveragePriority\]" simulations/omnetpp.ini
```

If not found, you need to split configs from master omnetpp.ini into scenario-specific files (Phase 9 task).

---

## 🚀 What to Do After First Success

### 1. Try Other Scenarios

```bash
# Urban grid scenario
./tools/run.sh UrbanGrid_Ensemble --sim-time-limit=120s

# Real-world scenario (takes longer)
./tools/run.sh ElectronicCity_Base --sim-time-limit=200s
```

### 2. Read Documentation

1. [docs/INDEX.md](docs/INDEX.md) — Documentation hub
2. [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — System design
3. [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md) — Detailed setup
4. [docs/tutorials/](docs/tutorials/) — Step-by-step guides (to be written)

### 3. Analyze Results

```bash
# Export to CSV
python tools/analysis/export-results.py results/Highway_*/

# Generate plots (requires pandas, matplotlib)
python tools/analysis/plot-residency.py results/
```

### 4. Next Development Tasks

- [ ] Fix any compilation errors
- [ ] Split scenario configs (highway/config.ini, urbangrid/config.ini, etc.)
- [ ] Write Python analysis tools
- [ ] Create GitHub Actions CI/CD
- [ ] Add unit tests
- [ ] Write 5 tutorials
- [ ] Publish to GitHub

---

## 📞 Need Help?

**Makefile issues?**  
→ See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) (to be written)

**Configuration questions?**  
→ See [docs/CONFIGURATION.md](docs/CONFIGURATION.md) (to be written)

**Want to extend the framework?**  
→ See [tutorials/03-custom-policy.md](docs/tutorials/03-custom-policy.md) (to be written)

---

## 📊 Success Metrics

You'll know everything is working when:

✅ `./tools/build.sh` completes in < 5 minutes  
✅ `./tools/run.sh Highway_CoveragePriority` produces results/  
✅ Results contain *.sca, *.vec, run-settings.ini  
✅ No compilation or runtime errors  
✅ You can run multiple scenarios without issues  

---

## 🎯 Phase Milestones

```
Phase 1-7 ✅  Repository structure, code migration, Git init
Phase 8   →  Makefile generation (NEXT)
Phase 9   →  First build & test
Phase 10  →  First simulation run
Phase 11  →  Fix any issues, split configs
Phase 12  →  Documentation completion
Phase 13  →  CI/CD setup
Phase 14  →  Python analysis tools
Phase 15  →  GitHub publication
```

---

**Ready to start? → Run Step 1 above!**

For detailed instructions, see [SETUP_COMPLETE.md](SETUP_COMPLETE.md).
