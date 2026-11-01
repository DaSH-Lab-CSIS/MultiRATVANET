# vsim-base

Pinned base image: OMNeT++ 6.3.0 · INET 4.6.0 · Veins 5.3.1 (+veins_inet) · Simu5G 1.7.0 · SUMO 1.22.0 on Ubuntu 22.04. No research repo inside.

    docker build -t vsim-base:om6.3.0-inet4.6.0-veins5.3.1-s5g1.7.0-sumo1.22.0 .
    docker build --build-arg JOBS=4 --build-arg RUN_SMOKE=0 ...      # small Docker VM / skip build-time smoke test

## Contract (v1)
- Toolchain root `/opt/vsim/{omnetpp,inet,veins,simu5g}` (unversioned paths; versions in `/opt/vsim/toolchain.json`, `vsim-versions`, and `dash.vsim.*` labels).
- Env: `OMNETPP_ROOT INET_ROOT VEINS_ROOT VEINS_INET_ROOT SIMU5G_ROOT SUMO_HOME`; `/opt/vsim/env.sh` loads the projects' own `setenv` (also via `BASH_ENV`).
- Repo goes in at `/workspace` (bind-mount, or `COPY` in a derived image). Write outputs to `/results`. Runs as non-root `vsim` (uid 1000; `--build-arg VSIM_UID`).
- Entrypoint: tini → `vsim-entrypoint`; starts `veins_launchd` on 127.0.0.1:9999 (`VSIM_LAUNCHD=0` to skip), then `exec "$@"`. Default CMD `bash`.
- TraCI: single container. Veins' `TraCIScenarioManagerLaunchd` → launchd → spawns `sumo`, all on loopback.
- Cmdenv only (no IDE, no Qtenv).

## Derive
    FROM vsim-base:om6.3.0-inet4.6.0-veins5.3.1-s5g1.7.0-sumo1.22.0
    COPY --chown=vsim:vsim . /workspace
    RUN ./build.sh        # RUN uses bash with toolchain env via ENV PATH + BASH_ENV

## OS / architecture invariance
Linux containers behave the same on Linux, macOS and Windows hosts; what varies is CPU arch. The image is built for `linux/amd64` and `linux/arm64`:

    docker buildx build --platform linux/amd64,linux/arm64 -t <registry>/vsim-base:<tag> --push .

- OMNeT++ ships per-arch tarballs; INET, Veins and Simu5G are built from source on each arch.
- SUMO 1.22.0 is built from the tagged source by default (`SUMO_INSTALL=source`), so both arches get identical SUMO. 1.22.0 is the version proven with Veins 5.3.1 on anjuna3 (Nix SUMO inside opp_env). `SUMO_INSTALL=auto|ppa` uses the PPA when the exact version exists.
- Newer SUMO needs `--build-arg VEINS_TRACI_CLAMP=1` (Veins 5.3.1 only knows TraCI API <=21); unverified, see Dockerfile.
- `.gitattributes` forces LF so the scripts don't break from a Windows checkout.
- Emulated cross-arch builds (e.g. arm64 on an x86 server) are very slow; build each arch natively and merge with a manifest list.

## Running with a mounted repo
The container user is uid 1000. To read/write a host folder owned by someone else, run as yourself:

    docker run --rm --user "$(id -u):$(id -g)" -v "$PWD":/workspace -v "$PWD/results":/results vsim-base:<tag> <command>

`vsim-versions` prints the toolchain lock as JSON on a clean stdout (launchd logs go to /tmp/veins_launchd.*).

## Permissions model
- Toolchain trees under /opt/vsim are world-writable *inside the container* so any `--user` uid can run tools that write next to themselves (e.g. Veins example `results/`). The build smoke-tests this as an arbitrary uid.
- Contract anyway: run repos from /workspace, write outputs to /results. /workspace and /results are mode 1777 (like /tmp); with a bind mount, host permissions apply.
