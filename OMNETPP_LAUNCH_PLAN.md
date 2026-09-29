# OMNeT++ Launch Methods - Updated

**Status:** Using external/ junction going forward  
**Old Location:** `d:\...\Simulation\omnetpp-5.6.1\bin\omnetpp.cmd` (redundant after external/)  
**New Location:** `d:\...\MultiRATVANET\external\omnetpp-5.6.1\bin\omnetpp.cmd` (via junction)  

---

## 🚀 Recommended: Launch via External Junction

This is the clean approach (no duplicate paths):

```powershell
# From MultiRATVANET directory
cd d:\Desktop_PCBackup\Mari-Per\PhD_Research\Federated_Learning\Course_Work\Work@2026\Simulation\MultiRATVANET

# Launch via external junction
.\external\omnetpp-5.6.1\bin\omnetpp.cmd
```

Or from anywhere:

```powershell
d:\Desktop_PCBackup\Mari-Per\PhD_Research\Federated_Learning\Course_Work\Work@2026\Simulation\MultiRATVANET\external\omnetpp-5.6.1\bin\omnetpp.cmd
```

---

## Create Convenient Shortcut Script

**New file: `tools/launch-omnetpp.bat`**

```batch
@echo off
REM Launch OMNeT++ IDE via external junction
cd /d "%~dp0.."
.\external\omnetpp-5.6.1\bin\omnetpp.cmd
```

**Then use:**
```powershell
.\tools\launch-omnetpp.bat
```

---

## Migration Plan

### Phase 1: Now (Document the junction)
- ✅ Use external/omnetpp-5.6.1 path going forward
- ✅ Create launch script using external path
- ✅ Update all documentation

### Phase 2: Later (Clean up)
- Remove or archive: `omnetpp-5.6.1` from Simulation root
- This frees up ~2.1 GB disk space
- External junction still works (points to backup or different location)

---

## Why This Is Better

| Aspect | Old Way | New Way |
|--------|---------|---------|
| **Location** | `Simulation/omnetpp-5.6.1` | `MultiRATVANET/external/omnetpp-5.6.1` (junction) |
| **Disk space** | Duplication | Single copy via junction |
| **Organization** | Framework external | Project-local external |
| **Portability** | Framework depends on sibling folder | Framework self-contained |
| **Cleanup** | Harder | Remove 2.1 GB when done |

---

## Updated Launch Commands

### Method 1: Via External Junction (RECOMMENDED)
```powershell
.\external\omnetpp-5.6.1\bin\omnetpp.cmd
```

### Method 2: Batch Script
```batch
.\tools\launch-omnetpp.bat
```

### Method 3: Via mingwenv (via external)
```powershell
.\external\omnetpp-5.6.1\mingwenv.cmd ide
```

---

## Delete Later

When ready to clean up disk space:

```powershell
# Remove the original (NOT the junction!)
Remove-Item -Path "..\omnetpp-5.6.1" -Recurse -Force

# Verify external junction still works
.\external\omnetpp-5.6.1\bin\omnetpp.cmd
```

---

## Next Steps

1. ✅ Use external/omnetpp-5.6.1 path going forward
2. ✅ Create launch script
3. ✅ Update git
4. 🔲 Later: Delete Simulation/omnetpp-5.6.1 (2.1 GB freed)

---

Generated: September 29, 2026  
Topic: OMNeT++ Launch Cleanup  
Status: Ready for implementation
