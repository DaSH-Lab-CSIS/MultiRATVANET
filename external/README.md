# External Frameworks Directory

This directory contains directory junctions (symbolic links) to the framework source directories needed by MultiRATVANET.

## Structure

```
external/
├── omnetpp-5.6.1/       → ../../omnetpp-5.6.1
├── inet-4.2.2/          → ../../inet-4.2.2-src/inet4
├── veins-5.2/           → ../../veins-5.2/veins-veins-5.2
└── simu5g-1.1.0/        → ../../Simu5G-1.1.0/Simu5G-1.1.0
```

## Why Junctions?

- **Cleaner paths** in build system and include statements
- **No duplication** of framework source code
- **Standard OMNeT++** directory structure
- **Portable** - works across projects

## Creating Junctions

### Windows (Admin Required)

```batch
cd external
mklink /J omnetpp-5.6.1 ..\..\omnetpp-5.6.1
mklink /J inet-4.2.2 ..\..\inet-4.2.2-src\inet4
mklink /J veins-5.2 ..\..\veins-5.2\veins-veins-5.2
mklink /J simu5g-1.1.0 ..\..\Simu5G-1.1.0\Simu5G-1.1.0
```

### Linux/macOS (Symbolic Links)

```bash
cd external
ln -s ../../omnetpp-5.6.1 .
ln -s ../../inet-4.2.2-src/inet4 inet-4.2.2
ln -s ../../veins-5.2/veins-veins-5.2 veins-5.2
ln -s ../../Simu5G-1.1.0/Simu5G-1.1.0 simu5g-1.1.0
```

## Verification

### List Junctions (Windows)

```batch
dir /A:L external\
```

You should see all four directories with `<JUNCTION>` next to them.

### List Symlinks (Linux/macOS)

```bash
ls -la external/
```

You should see all four entries with `->` pointing to targets.

## Build System Fallback

The `GNUmakefile` automatically:
1. **Tries** `external/inet-4.2.2`, etc. (with junctions)
2. **Falls back** to `../inet-4.2.2-src/inet4` (if junctions missing)
3. **Works without admin** privileges

So even if you can't create junctions, the build will still succeed.

## Troubleshooting

### "Cannot create junction" (Windows)

**Solution:** Run terminal as Administrator

### "Permission denied" (Linux/macOS)

**Solution:** Ensure write permissions in `external/` directory
```bash
chmod u+w external/
```

### Build still fails to find frameworks

**Check:** GNUmakefile paths are correct
```bash
grep "INET_PATH\|VEINS_PATH\|SIMU5G_PATH" ../framework/GNUmakefile
```

## Notes

- Junctions are **platform-specific** (Windows) vs symlinks (Unix)
- They are **lightweight** - no duplication of files
- Git tracks the directory structure (via `.gitkeep`), but not the junction targets themselves
- Removing a junction doesn't affect the original files

## See Also

- [GNUmakefile](../framework/GNUmakefile) - Framework path resolution
- [GETTING_STARTED.md](../docs/GETTING_STARTED.md) - Build instructions
- [ARCHITECTURE.md](../docs/ARCHITECTURE.md) - System architecture
