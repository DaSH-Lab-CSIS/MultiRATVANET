# external/

Not used by the current build. `tools/build.sh` and `tools/run.sh` find OMNeT++, INET, Veins and
Simu5G through the environment variables `OMNETPP_BIN`, `INET_DIR`, `VEINS_DIR` and `SIMU5G_DIR`
(see [docs/GETTING_STARTED.md](../docs/GETTING_STARTED.md)); the Docker image sets them for you.

The folder is kept, and git-ignored except for this file, for anyone who prefers to keep local
symlinks to their toolchain checkouts here and point the variables at them.
