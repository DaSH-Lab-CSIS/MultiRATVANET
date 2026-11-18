# MultiRATVANET Framework

**Multi-RAT VANET Handover Simulation Framework** for OMNeT++ / Veins / SUMO / INET / Simu5G

A vehicle carries multiple radio access technologies (DSRC, WiFi, 5G-NR) simultaneously, all terminating at a unified IPv4 stack. An application-layer RAT selector orchestrates handovers based on configurable policies, enabling research into multi-RAT vehicular network optimization.

## Quick Start (Docker)

Everything (toolchain and framework) is in one Docker image. You only need Docker and this repo.

```bash
# Build the image (first time: 1-2 h, it compiles the whole toolchain)
dash/build-image.sh

# Run one config, results go to ./results
dash/mrv run Sinr --sim-time-limit=120s

# Run an experiment with parameters, then open results/report.html
dash/run-experiment.sh --scenario highway --policy ensemble --time 120s --ensemble-weight-sinr 2
```

Use `DOCKER="sudo docker"` in front of any of these if your user is not in the `docker` group.

## Documentation

- **[Getting Started](docs/GETTING_STARTED.md)** — build and first run, with or without Docker
- **[Policy Reference](docs/POLICY_REFERENCE.md)** — writing a RAT selection policy: inputs, outputs, example
- **[Architecture](docs/ARCHITECTURE.md)** — modules, policies, metrics, scenarios, parameters
- **[Toolchain image](docker/base/README.md)** — the pinned base image and its patches

## Features

- **RATs:** DSRC and WiFi (802.11 to roadside units / access points) and 5G-NR (Simu5G), all on one IPv4 stack; a 6G placeholder interface
- **Policies:** CoveragePriority, Sinr, LatencyQos, Load, Ensemble (weighted vote of those four), and Ml, a hook for an external learned controller (no controller is included, so on its own it decides like CoveragePriority). ExampleSplit is a template for writing your own
- **Car-side inputs:** a policy sees only what its own car knows: position, connection, per-RAT signal, sensed load and link rate, the round trip and loss of its own probes, and the replies to its own traffic
- **Scenarios:** Highway, UrbanGrid (synthetic), ElectronicCity (real OSM), plus V2V beaconing over ad-hoc DSRC and C-V2X sidelink broadcast
- **Traffic and KPIs:** two-way, request-and-reply: safety messages the server acknowledges, and infotainment data the server sends on request. A policy can put each class on its own RAT. Delivery, delay, deadline, throughput, handovers, ping-pong, time on each RAT, outage, and the interruption each switch causes
- **Docker:** one image with the pinned toolchain; an experiment runner and an HTML report

## Prerequisites

With Docker: Docker 20.10+ (Linux, or Docker Desktop on macOS/Windows). The image is x86_64; on an ARM Mac it runs under emulation, slower.

Without Docker, build these yourself (versions must match):

- **OMNeT++ 6.3.0**
- **INET 4.6.0**, with `docker/base/patches/inet-4.6.0-dash.patch`
- **Veins 5.3.1** + veins_inet
- **Simu5G 1.7.0**, with `docker/base/patches/simu5g-1.7.0-dash.patch` (without it the cellular path delivers nothing)
- **SUMO 1.22.0** (Veins 5.3.1 does not support newer TraCI versions)

## Repository Structure

```
framework/src/multirat/   The framework (C++ and NED)
├── base/                 RAT ids, per-RAT metrics, and the policy request/response types
├── core/                 MultiRatCar, WifiAp, DsrcRsu, 6G placeholder interface
├── monitor/              RatCoverageMonitor: per-RAT signal, sensed load, link rate, in range
├── manager/              MultiRatAppManager (decides and switches), RatStatsCollector
├── policies/             RAT selection policies
├── apps/                 Traffic app, probe app, server sink, V2V beacon app
└── _ned/                 Links to all NED files in one folder (the NED path used by tools/run.sh)
simulations/
├── omnetpp.ini           All configs
├── router.mrt            The core router's routes back to the cars' DSRC and WiFi addresses
├── networks/             Network topologies (NED)
└── scenarios/            SUMO network, routes and launch files per scenario
sumo/                     Source files the SUMO scenarios were generated from
tools/                    build.sh, run.sh, sumo-launchd.sh
dash/                     Docker image, experiment runner, HTML report, dashboard manifest
docker/base/              Pinned toolchain image (OMNeT++, INET, Veins, Simu5G, SUMO) and patches
docs/                     Documentation
```

## Build & Run

### With Docker

| Command | What it does |
|---|---|
| `dash/build-image.sh` | Builds `vsim-base` (toolchain, from `docker/base/`) if missing, then `multiratvanet:<commit>` and `:latest`. The build fails if a 15 s cellular test run delivers nothing. `JOBS=4` limits compile jobs on small machines. |
| `dash/mrv run <CONFIG> [--sim-time-limit=T] ['--<ini-key>=<value>' ...]` | Runs one config from `simulations/omnetpp.ini`. |
| `dash/mrv shell` | Bash inside the image, toolchain on PATH. |
| `dash/mrv versions` | Toolchain versions and repo commit baked into the image. |
| `dash/run-experiment.sh --help` | Runs one experiment with every tunable as a flag (scenario, policy, time, seed, ranges, ensemble weights, `--set KEY=VALUE`), saves `run.json` and `console.log`, and rebuilds `results/report.html`. |

`results/report.html` lists every run with its scenario and config, final results (delivery, throughput, delay, handovers), time series and console log. Open it in a browser; `report.html#<run-folder>` links to one run.

To use the image on another machine without building it:

```bash
docker save multiratvanet:latest | gzip > multiratvanet.tar.gz   # on a machine that has it
docker load < multiratvanet.tar.gz                              # on the new machine
```

If GitHub downloads fail during the build, put the release tarballs in `docker/base/dl/`; see `docker/base/README.md`.

### Without Docker

`tools/build.sh` and `tools/run.sh` read `OMNETPP_BIN`, `INET_DIR`, `VEINS_DIR` and `SIMU5G_DIR` from the environment. Start the TraCI launch daemon first and leave it running (`tools/sumo-launchd.sh`, port 9999).

```bash
./tools/build.sh
./tools/run.sh Ensemble --sim-time-limit=120s
```

`tools/run.sh <CONFIG>` uses the config's own `sim-time-limit` unless `--sim-time-limit=` is given, runs every run of the config (`--run=N` picks one of a parameter study such as `EnsembleSweep`), and passes any other `--<ini-key>=<value>` to the simulation. Results go to `results/<CONFIG>_<timestamp>/` (or under `$RESULTS_ROOT`).

## Configuration

All configs are in `simulations/omnetpp.ini`:

```
CoveragePriority, Sinr, LatencyQos, Load, Ml, Ensemble    Highway, one per policy
EnsembleSweep                                             Highway, 9 runs over the ensemble weights
DsrcNrHandover, V2V, CV2X                                 Highway variants
UrbanGrid_CoveragePriority, UrbanGrid_Ensemble, UrbanGrid_ML
ElectronicCity_CoveragePriority, ElectronicCity_Ensemble, ElectronicCity_ML
```

- **Vehicles:** the number comes from the SUMO route file of the scenario (`simulations/scenarios/<scenario>/*.rou.xml`), not from the ini.
- **Cellular is one RAT, 5G-NR.** The networks have gNodeBs only, so LTE is switched off (`hasLte = false`). `DsrcLteHandover` is kept as an old name of `DsrcNrHandover`.
- **Probing** (`*.car[*].app[2].probeInterval`, 100 ms): every car probes every linked RAT; a RAT is usable only while the server's echoes come back (`*.car[*].ratCoverageMonitor.probeMaxAge`, 0.5 s).
- **Policy tunables** (`*.car[*].multiRatAppManager.*`): `decisionInterval`, `timeToTrigger`, `sinrSwitchMargin`, `loadSwitchMargin`, `latencyBudget`, the `ensembleWeight*` values and `ensembleStickiness`. See [Architecture](docs/ARCHITECTURE.md).
- **Infrastructure positions, traffic classes and radio settings** are in the `[General]` section and the scenario base configs.

## Results

Each run writes to its own folder:

```
results/<run>/
├── run-settings.ini         Copy of omnetpp.ini as it was run
├── *.sca                    Scalars (per-car and per-class KPIs)
└── *.vec, *.vci             Time series
```

`dash/run-experiment.sh` adds `run.json` and `console.log` per run and rebuilds `results/report.html`, which compares all runs. To rebuild the report by hand: `python3 dash/report.py results`.

## License

Research license — see [LICENSE](LICENSE)

## Citation

If you use MultiRATVANET in your research, please cite:

```
[Your citation here when published]
```

---

**Built with:** OMNeT++ • INET • Veins • Simu5G • SUMO
