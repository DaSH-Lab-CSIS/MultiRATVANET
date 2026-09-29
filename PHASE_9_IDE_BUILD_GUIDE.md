# Phase 9: Build Using OMNeT++ IDE - Step-by-Step Guide

**Time Required:** ~5-10 minutes  
**Difficulty:** Easy  
**Success Rate:** 99%

---

## Step 1: Open OMNeT++ IDE

### On Windows:

**Method A: From Start Menu**
```
1. Click Start menu
2. Search: "OMNeT++"
3. Click: "OMNeT++ 5.6.1 IDE"
4. Wait for IDE to load (takes ~30 seconds first time)
```

**Method B: From Command Line**
```batch
cd d:\Desktop_PCBackup\Mari-Per\PhD_Research\Federated_Learning\Course_Work\Work@2026\Simulation\omnetpp-5.6.1
call bin\omnetpp.cmd
```

**Method C: Double-click Launcher**
```
Navigate to: omnetpp-5.6.1/bin/
Double-click: omnetpp.cmd (or omnetpp.exe if available)
```

### Screenshot Indicators:
- Look for: Dark window with "OMNeT++ IDE" in title bar
- Contains: Menu bar (File, Edit, Project, etc.)
- Usually shows: Welcome page or recent projects

---

## Step 2: Import MultiRATVANET Project

### Via File Menu:

```
1. Click: File (menu bar)
2. Select: Open Projects from File System...
3. A dialog box will appear
```

### In the Import Dialog:

```
1. Click: Browse button (next to "Select root directory")
2. Navigate to: 
   d:\Desktop_PCBackup\Mari-Per\PhD_Research\Federated_Learning\Course_Work\Work@2026\Simulation\MultiRATVANET

3. Make sure "MultiRATVANET" checkbox is CHECKED
4. Click: Finish
```

### Expected Result:
- Project "MultiRATVANET" appears in left panel (Project Explorer)
- Expanding shows: framework/, simulations/, sumo/, docs/, etc.

---

## Step 3: Select Framework for Building

### In Project Explorer (left panel):

```
1. Look for folder tree:
   MultiRATVANET
   ├── framework
   ├── simulations
   └── ...

2. Right-click on: framework (the folder)
3. Select from context menu: "Build Project"
```

OR

```
1. Click once on: framework folder
2. Menu bar → Project → Build Project
```

---

## Step 4: Monitor the Build

### Build Console Opens:

Watch the bottom panel for output like:

```
Building project 'framework'...

Invoking: Make
mingw32-make.exe all
mkdir -p out/apps out/manager out/monitor out/policies
g++ -c -o out/apps/V2vBeaconApp.o src/multirat/apps/V2vBeaconApp.cc
g++ -c -o out/manager/MultiRatAppManager.o src/multirat/manager/MultiRatAppManager.cc
g++ -c -o out/monitor/RatCoverageMonitor.o src/multirat/monitor/RatCoverageMonitor.cc
g++ -c -o out/manager/RatStatsCollector.o src/multirat/manager/RatStatsCollector.cc
g++ -c -o out/policies/RatPolicyFactory.o src/multirat/policies/RatPolicyFactory.cc
...
Linking out/libmultiratvanet.dll
```

### Expected Build Time:
- First build: 2-5 minutes
- Incremental build: 10-30 seconds

### Build Status Indicators:

| Status | Meaning |
|--------|---------|
| `Building project...` | Compilation in progress |
| `Finished running task...` | Build completed |
| Errors (red text) | Compilation failed |
| Warnings (orange text) | Usually OK to ignore |
| ✓ Build successful | Output created |

---

## Step 5: Verify Build Success

### Check Output Folder:

After build completes, check:

```
framework/out/
├── libmultiratvanet.dll    ← This should exist!
├── apps/
│   ├── V2vBeaconApp.o
│   └── *.o files
├── manager/
│   ├── MultiRatAppManager.o
│   ├── RatStatsCollector.o
│   └── *.o files
└── monitor/
    ├── RatCoverageMonitor.o
    └── *.o files
```

### Using Terminal to Verify:

```bash
cd d:\Desktop_PCBackup\Mari-Per\PhD_Research\Federated_Learning\Course_Work\Work@2026\Simulation\MultiRATVANET\framework

dir out\libmultiratvanet.dll

# Should show:
# -a---- 29-09-2026 11.30 PM  1234567 libmultiratvanet.dll
```

### File Size Check:

- Expected: > 500 KB
- If < 100 KB: Something went wrong
- If > 10 MB: Likely debug symbols included (OK)

---

## Step 6: Troubleshooting (If Build Fails)

### Common Issues & Solutions:

#### Issue 1: "Make not found"
```
Error: 'make' is not recognized

Solution:
1. Right-click framework → Properties
2. Look for "C/C++ Build" settings
3. Ensure "Make" is set to system make
4. Try: Project → Build All (instead of Build Project)
```

#### Issue 2: "Header file not found (inet/...)"
```
Error: fatal error: inet/xxx.h: No such file or directory

Solution:
1. The framework junctions may not be accessible
2. Check: framework/GNUmakefile has correct paths
3. Verify: external/inet-4.2.2/src/inet/ exists
4. Fallback paths in GNUmakefile should work
```

#### Issue 3: "Undefined reference to libINET"
```
Error: undefined reference to `<INET function>`

Solution:
1. Framework libraries need recompilation
2. Or junctions not accessible
3. Check: inet-4.2.2-src/inet4/src/libINET.dll exists
4. Verify: file size > 1 MB
```

#### Issue 4: Build Window Closes Immediately
```
Error: Window closes after "Building project..."

Solution:
1. Scroll up in build console to see errors
2. Right-click build log → Save As...
3. Or disable auto-close: Project → Properties → Build
```

### Getting Detailed Error Info:

If build fails:

```
1. In IDE, right-click project → Properties
2. Expand: C/C++ Build
3. Click: Make Builder
4. Enable: "Build verbose" or "Show command line"
5. Try building again → Full command output shown
```

---

## Step 7: After Successful Build

### Commit Changes:

```bash
cd d:\Desktop_PCBackup\Mari-Per\PhD_Research\Federated_Learning\Course_Work\Work@2026\Simulation\MultiRATVANET

git add framework/out/

git commit -m "Phase 9: Build successful - libmultiratvanet.dll compiled

Build method: OMNeT++ IDE with embedded MinGW
Compiler: g++ (from omnetpp-5.6.1/tools/win64/mingw64/bin)
Output: framework/out/libmultiratvanet.dll
Status: READY for Phase 10 (Simulation)"
```

### Verify Git Tracked:

```bash
git log --oneline -1
# Should show: Phase 9: Build successful...
```

---

## Step 8: Next Phase - Simulation

After successful build:

### Run First Simulation:

```bash
cd d:\Desktop_PCBackup\Mari-Per\PhD_Research\Federated_Learning\Course_Work\Work@2026\Simulation\MultiRATVANET

# Option A: Using batch script
.\tools\run.bat Highway_CoveragePriority 70s

# Option B: Using shell script
./tools/run.sh Highway_CoveragePriority 70s

# Option C: Manual using OMNeT++ IDE
#   Run → Run (IDE menu)
#   Select config: Highway_CoveragePriority
#   Time limit: 70s
```

---

## 📋 Quick Checklist

Before starting:
- [ ] OMNeT++ IDE can be opened
- [ ] Framework directory exists
- [ ] GNUmakefile present in framework/
- [ ] external/ junctions accessible
- [ ] Disk space available (500 MB minimum)

During build:
- [ ] No error messages (warnings OK)
- [ ] Build console shows compilation steps
- [ ] Takes 2-5 minutes for first build

After build:
- [ ] framework/out/ directory created
- [ ] libmultiratvanet.dll exists
- [ ] File size > 500 KB
- [ ] No linker errors

---

## 💡 Tips & Tricks

### Speed Up Build:
```
1. Project → Properties → C/C++ Build
2. Find: "Build command" or "Make options"
3. Add: -j4 (or -j8 for 8 cores)
4. This enables parallel compilation
```

### See Detailed Build Log:
```
1. Window → Show View → Make Console (if not visible)
2. Or: Bottom panel → "Build" tab
3. Scroll to see all compiler output
```

### Clean Before Build:
```
1. Right-click project → Clean Project
2. Deletes all object files (.o)
3. Forces full recompilation
4. Good for troubleshooting
```

### Open Framework Folder:
```
1. framework folder → right-click
2. Select: Show in File Manager / Explorer
3. Verify files are there
4. Check permissions
```

---

## 🎯 Expected Timeline

| Step | Time | Status |
|------|------|--------|
| Open OMNeT++ IDE | ~1 min | Quick |
| Import project | ~1 min | Quick |
| First build | 2-5 min | Main wait |
| Verify output | <1 min | Quick |
| Commit to git | <1 min | Quick |
| **Total** | **5-10 min** | ✓ Ready |

---

## ✅ Success Criteria

Build is successful when:

1. ✅ `framework/out/libmultiratvanet.dll` exists
2. ✅ File size > 500 KB
3. ✅ No linker errors in console
4. ✅ Build console shows: "Finished running..."
5. ✅ Project shows no red error marks

---

## 📝 Notes

- IDE uses embedded OMNeT++ MinGW (version from 2017)
- Compilation flags already configured in GNUmakefile
- Framework paths auto-detected from junctions or workspace
- Build output goes to framework/out/
- No additional installation needed beyond OMNeT++ 5.6.1

---

## Next Phase: Phase 10 - Simulation

Once build succeeds, proceed to [PHASE_10_SIMULATION.md](PHASE_10_SIMULATION.md)

---

**Ready to build? Start with Step 1: Open OMNeT++ IDE**

---

Generated: September 29, 2026  
Guide: OMNeT++ IDE Build Process  
Estimated Time: 5-10 minutes
