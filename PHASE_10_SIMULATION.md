# Phase 10: First Simulation Run - Complete Guide

**Prerequisite:** Phase 9 build must be complete (libmultiratvanet.dll exists)  
**Time Required:** ~10-15 minutes  
**Difficulty:** Easy

---

## Overview: What Happens During Simulation

```
┌─────────────────────────────────────────────────────┐
│   OMNeT++ Simulation Engine                         │
│  (runs MultiRATVANET C++ code)                      │
│                                                      │
│   Loads: libmultiratvanet.dll                       │
│   Config: simulations/omnetpp.ini                   │
│   Topology: simulations/networks/*.ned              │
│   Scenario: Highway_CoveragePriority                │
│                                                      │
│   Calls TraCI Interface ↓                           │
└─────────────────────────────────────────────────────┘
              ↓ (Socket on port 9998)
┌─────────────────────────────────────────────────────┐
│   SUMO Traffic Simulator (Java)                     │
│  (Provides vehicle positions & mobility)            │
│                                                      │
│   Loads: sumo/highway/Straight_Lane.sumocfg         │
│   Network: sumo/highway/Straight_Lane.net.xml       │
│   Routes: sumo/highway/Straight_Lane.rou.xml        │
│                                                      │
│   Returns vehicle positions & sensor data ↑        │
└─────────────────────────────────────────────────────┘
              ↑ (Socket on port 9998)
```

---

## Step 1: Pre-Simulation Checklist

Before running simulation, verify:

### Build Artifacts
```bash
cd d:\Desktop_PCBackup\Mari-Per\PhD_Research\Federated_Learning\Course_Work\Work@2026\Simulation\MultiRATVANET

# Verify DLL exists
ls framework/out/libmultiratvanet.dll

# Expected output:
# -a---- 29-09-2026 11.30 PM  1234567 libmultiratvanet.dll
```

### Simulation Configuration Files
```bash
# Check omnetpp.ini exists
ls simulations/omnetpp.ini

# Check network definition
ls simulations/networks/MultiRatHighway.ned

# Check SUMO scenario files
ls sumo/highway/
# Expected: Straight_Lane.sumocfg, .net.xml, .rou.xml
```

### Checkpoints:
- [ ] `framework/out/libmultiratvanet.dll` exists (size > 500 KB)
- [ ] `simulations/omnetpp.ini` exists
- [ ] `simulations/networks/MultiRatHighway.ned` exists
- [ ] `sumo/highway/Straight_Lane.sumocfg` exists
- [ ] `sumo-1_24_0/bin/sumo.exe` exists (SUMO executable)

---

## Step 2: Run Simulation Using Script

### Option A: Using Batch Script (Recommended)

```batch
cd d:\Desktop_PCBackup\Mari-Per\PhD_Research\Federated_Learning\Course_Work\Work@2026\Simulation\MultiRATVANET

# Run Highway scenario with CoveragePriority policy for 70 seconds
.\tools\run.bat Highway_CoveragePriority 70s
```

### Option B: Using Shell Script (Linux/macOS)

```bash
cd d:\Desktop_PCBackup\Mari-Per\PhD_Research\Federated_Learning\Course_Work\Work@2026\Simulation\MultiRATVANET

# Run Highway scenario
./tools/run.sh Highway_CoveragePriority 70s
```

### Option C: Using PowerShell

```powershell
cd d:\Desktop_PCBackup\Mari-Per\PhD_Research\Federated_Learning\Course_Work\Work@2026\Simulation\MultiRATVANET

# Direct PowerShell execution
& ".\tools\run.bat" "Highway_CoveragePriority" "70s"
```

---

## Step 3: Monitor Simulation Progress

### What You'll See:

```
Starting SUMO daemon...
SUMO listening on port 9998
Waiting for OMNeT++ to connect...

Launching OMNeT++ Simulation...
Simulation Name: Highway_CoveragePriority
Time Limit: 70 seconds
Vehicles: 3
Network: MultiRatHighway (2km highway, 2 gNodeBs, 2 APs, 3 RSUs)

Running...
 0s: Vehicle1 connects to 5G (gNodeB_1), SINR=15dB
 5s: Vehicle2 connects to WiFi (AP_1), RSSI=-50dBm
10s: Vehicle1 handover 5G→WiFi, latency=15ms
15s: Vehicle3 coverage check...

...simulation progresses...

70s: Simulation ended
Total handovers: 12
Handover success rate: 95.8%

Collecting results...
Results saved to: results/Highway_CoveragePriority_20260929_113045/
```

### Key Indicators:

| Output | Meaning |
|--------|---------|
| `SUMO listening on port 9998` | SUMO daemon started correctly |
| `Running...` | OMNeT++ simulation progressing |
| `Simulation ended` | Successfully completed |
| `Results saved to...` | Output files created |
| `Connection refused` on port 9998 | SUMO failed to start |
| `Cannot find omnetpp.ini` | Configuration file missing |

---

## Step 4: Verify Output

### After simulation completes, check results:

```bash
cd d:\Desktop_PCBackup\Mari-Per\PhD_Research\Federated_Learning\Course_Work\Work@2026\Simulation\MultiRATVANET

# List results directory
ls results/

# Expected output:
# Highway_CoveragePriority_20260929_113045/
# Highway_CoveragePriority_20260929_115230/
# ...
```

### Contents of Results Folder:

```
results/Highway_CoveragePriority_<timestamp>/
├── run-settings.ini              ← Configuration snapshot
├── Highway_CoveragePriority.sca   ← Statistics (scalar values)
├── Highway_CoveragePriority.vec   ← Vectors (time series)
├── Highway_CoveragePriority.out   ← Simulation output log
└── analysis/                      ← (Optional) Analysis results
    ├── summary.csv
    └── plots/
```

### Verify Files:

```bash
# Check if results were created
ls -la results/Highway_CoveragePriority_*/

# Expected:
# run-settings.ini  (100 bytes)
# *.sca             (50-500 KB)
# *.vec             (100 KB - 10 MB)
# *.out             (10-100 KB)
```

---

## Step 5: Analyze Results

### Quick Statistics:

```bash
# Open run-settings.ini to see what was simulated
cat results/Highway_CoveragePriority_<latest>/run-settings.ini

# Sample output:
[General]
network = MultiRatHighway
sim-time-limit = 70s
policy = CoveragePriority
vehicles = 3
```

### View Simulation Output:

```bash
# View the simulation log
cat results/Highway_CoveragePriority_<latest>/Highway_CoveragePriority.out

# Sample lines:
# 0.000000s: Vehicle0 initialized at position (100, 50)
# 0.500000s: Vehicle0 connected to 5G (gNodeB_1)
# 1.234567s: Vehicle0 scanned RATs: 5G(15dB), WiFi(-48dBm), DSRC(OK)
# ...
```

### Parse Statistics (Advanced):

```bash
# Using grep to extract handover events
grep "handover\|Handover\|HANDOVER" results/Highway_CoveragePriority_<latest>/*.out

# Count handovers
grep -c "handover" results/Highway_CoveragePriority_<latest>/*.out
```

---

## Step 6: Troubleshooting

### Issue 1: "SUMO not found"
```
Error: Cannot find sumo.exe or sumo not in PATH

Solution:
1. Verify: sumo-1_24_0/bin/sumo.exe exists
2. Check: tools/run.bat contains correct path
3. Update: set SUMO_HOME=...sumo-1_24_0
```

### Issue 2: "Cannot connect to SUMO on port 9998"
```
Error: Connection refused / SUMO daemon not started

Solution:
1. Port 9998 may be in use by another program
2. Kill previous SUMO: taskkill /im sumo.exe /f
3. Wait 5 seconds, try again
4. Or use different port in omnetpp.ini
```

### Issue 3: "Configuration not found: Highway_CoveragePriority"
```
Error: Cannot find config in omnetpp.ini

Solution:
1. Check: simulations/omnetpp.ini exists
2. Verify: [Config Highway_CoveragePriority] section exists
3. Check: Network topology matches
4. Look at: docs/GETTING_STARTED.md for config names
```

### Issue 4: "libmultiratvanet.dll not found"
```
Error: Cannot load compiled library

Solution:
1. Rebuild: Phase 9 build (framework/out/libmultiratvanet.dll)
2. Verify: DLL exists and is > 500 KB
3. Check: omnetpp.ini points to correct DLL location
```

### Issue 5: "Simulation takes too long / hangs"
```
Error: Simulation runs but seems stuck

Solution:
1. Increase timeout: Run with longer time limit first
2. Check SUMO connectivity: sumo.exe should be running
3. Monitor ports: Check if port 9998 is active
4. View logs: Look at simulations/Highway_CoveragePriority.out
```

---

## Step 7: Run Multiple Scenarios

After first successful run:

### Try Other Scenarios:

```bash
# Urban Grid scenario
.\tools\run.bat UrbanGrid_Ensemble 70s

# Electronic City scenario (realistic)
.\tools\run.bat ElectronicCity_ML 70s

# All scenarios (automated sweep)
.\tools\run-all-scenarios.sh
```

### Available Configurations:

```
Highway scenarios:
  - Highway_CoveragePriority
  - Highway_SINR
  - Highway_LatencyQos
  - Highway_Ensemble

UrbanGrid scenarios:
  - UrbanGrid_CoveragePriority
  - UrbanGrid_Ensemble
  - UrbanGrid_LoadBalanced

ElectronicCity scenarios:
  - ElectronicCity_CoveragePriority
  - ElectronicCity_ML
  - ElectronicCity_Ensemble
```

---

## Step 8: Collect Results for Comparison

After running multiple scenarios:

```bash
# View all results
ls -la results/

# Compare metrics across runs
python tools/analysis/export-results.py results/

# Plot residency across scenarios
python tools/analysis/plot-residency.py results/

# Generate comparison report
python tools/analysis/compare-policies.py results/
```

---

## Step 9: Commit Results to Git

### Save Run Results:

```bash
cd d:\Desktop_PCBackup\Mari-Per\PhD_Research\Federated_Learning\Course_Work\Work@2026\Simulation\MultiRATVANET

# Add results (but not .vec/.sca files - they're large)
git add results/*/run-settings.ini results/*/*.out

# Commit
git commit -m "Phase 10: First simulation run successful

Scenario: Highway_CoveragePriority
Duration: 70 seconds
Vehicles: 3
Results:
  ✓ Handovers detected
  ✓ RAT selection working
  ✓ Statistics collected
  ✓ Output files generated

Results location:
  results/Highway_CoveragePriority_<timestamp>/

Status: Ready for analysis phase"
```

---

## 📋 Phase 10 Checklist

Before starting:
- [ ] Phase 9 build complete
- [ ] libmultiratvanet.dll exists
- [ ] simulations/omnetpp.ini ready
- [ ] sumo/highway/ scenario files present
- [ ] SUMO executable found

During simulation:
- [ ] SUMO daemon starts
- [ ] OMNeT++ connects
- [ ] Simulation shows progress
- [ ] No fatal errors

After simulation:
- [ ] results/ folder created
- [ ] .sca file generated (100 KB+)
- [ ] .vec file generated (1 MB+)
- [ ] .out file has data
- [ ] run-settings.ini logged

---

## 🎯 Success Indicators

Simulation succeeded when:

1. ✅ `results/Highway_CoveragePriority_<timestamp>/` folder created
2. ✅ `.sca` file exists (size > 50 KB)
3. ✅ `.vec` file exists (size > 100 KB)
4. ✅ `.out` log shows simulation events
5. ✅ `run-settings.ini` documents config
6. ✅ No error messages in console

---

## 📊 Expected Output

### Sample run-settings.ini:
```
[General]
network = MultiRatHighway
sim-time-limit = 70s
policy = CoveragePriority
vehicles = 3

[Network]
gNodeBs = 2
WiFi_APs = 2
DSRC_RSUs = 3

[Results]
handover_count = 12
handover_success_rate = 95.8%
avg_residency_time = 15.3s
```

### Sample .out excerpt:
```
0.000000s: Simulation started
0.001234s: Vehicle0 initialized
0.002500s: Vehicle0 scanned coverage
0.005000s: Vehicle0 connected to 5G (gNodeB_1)
1.234567s: Vehicle1 handover: 5G→WiFi
...
70.000000s: Simulation ended
```

---

## 🔄 Next Steps After Phase 10

### If simulation succeeds:
- ✅ Phase 11: Analyze results
- ✅ Phase 12: Run with different policies
- ✅ Phase 13: Write research findings

### If simulation fails:
- Review troubleshooting section above
- Check [PHASE_9_CROSS_CHECK.md](PHASE_9_CROSS_CHECK.md)
- Verify [GETTING_STARTED.md](docs/GETTING_STARTED.md)

---

## 💡 Tips

### Record Run:
```bash
# Save console output to file
.\tools\run.bat Highway_CoveragePriority 70s > run_log.txt 2>&1
```

### Test Configuration:
```bash
# Test with short time (5s) before long runs
.\tools\run.bat Highway_CoveragePriority 5s
```

### Debug SUMO:
```bash
# Run SUMO in GUI mode to see vehicles
sumo-gui -c sumo/highway/Straight_Lane.sumocfg
```

### Increase Logging:
```bash
# In simulations/omnetpp.ini, add:
[General]
debug-on-errors = true
record-event-log = true
```

---

## Summary

| Phase | Step | Status |
|-------|------|--------|
| 9 | Build using OMNeT++ IDE | ✅ Complete |
| 10 | Run simulation | 👈 **You are here** |
| 10 | Verify output | Next |
| 10 | Analyze results | Optional |
| 11 | Multiple scenarios | After Phase 10 |
| 12 | Generate reports | After Phase 11 |

---

**Ready to run simulation? Execute: `.\tools\run.bat Highway_CoveragePriority 70s`**

---

Generated: September 29, 2026  
Guide: Phase 10 First Simulation  
Estimated Time: 10-15 minutes
