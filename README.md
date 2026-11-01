# MultiRATVANET Framework

**Multi-RAT VANET Handover Simulation Framework** for OMNeT++ / Veins / SUMO / INET / Simu5G

A vehicle carries multiple radio access technologies (DSRC, WiFi, LTE, 5G-NR) simultaneously, all terminating at a unified IPv4 stack. An application-layer RAT selector orchestrates handovers based on configurable policies, enabling research into multi-RAT vehicular network optimization.

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

- **[Getting Started](docs/GETTING_STARTED.md)** — Installation & first run
- **[Architecture](docs/ARCHITECTURE.md)** — System design overview
- **[Scenarios](docs/scenarios/)** — Highway, UrbanGrid, ElectronicCity
- **[Configuration](docs/CONFIGURATION.md)** — Parameter reference
- **[API Reference](docs/api/)** — Module & policy interfaces
- **[Tutorials](docs/tutorials/)** — Step-by-step guides

## Features

- ✅ **Multiple RATs:** DSRC, WiFi, LTE, 5G-NR, 6G placeholder
- ✅ **Flexible policies:** Coverage Priority, SINR-based, Latency-QoS, Load-Balanced, Ensemble Voting, ML-driven
- ✅ **Realistic scenarios:** Highway (baseline), UrbanGrid (synthetic), ElectronicCity (real OSM)
- ✅ **Full V2X support:** CAM/DENM broadcasts, V2N upload/download
- ✅ **Comprehensive KPIs:** Handover count, latency, ping-pong ratio, RAT residency, packet loss
- ✅ **Automated tools:** Single-command build & run
- ✅ **CI/CD ready:** GitHub Actions workflows included
- ✅ **Docker support:** Reproducible environment

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
framework/               Core MultiRATVANET code
├── src/multirat/
│   ├── base/           Types, metrics, constants
│   ├── core/           NED nodes & networks
│   ├── monitor/        Coverage, SINR, latency detection
│   ├── manager/        Handover logic & statistics
│   ├── policies/       RAT selection strategies
│   └── apps/           V2V, V2X applications

simulations/            OMNeT++ simulation config
├── networks/           Network topologies (NED)
├── scenarios/          Configuration by scenario (INI)
└── omnetpp.ini        Master configuration

sumo/                   SUMO traffic models
├── highway/
├── urbangrid/
└── electroniccity/

docs/                   Comprehensive documentation
tools/                  Build, run, analysis automation
tests/                  Unit & integration tests
results/                Experiment results & analysis
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

`tools/build.sh` and `tools/run.sh` read `OMNETPP_BIN`, `INET_DIR`, `VEINS_DIR` and `SIMU5G_DIR` from the environment. Start `veins_launchd -c sumo -p 9999` from the repo root first.

```bash
./tools/build.sh
./tools/run.sh Ensemble --sim-time-limit=120s
```

## Configuration

Each scenario has multiple configurations:

```
CoveragePriority, Sinr, LatencyQos, Load, Ml, Ensemble    Highway, one per policy
DsrcLteHandover, V2V, CV2X                                Highway variants
UrbanGrid_CoveragePriority, UrbanGrid_Ensemble, UrbanGrid_ML
ElectronicCity_CoveragePriority, ElectronicCity_Ensemble, ElectronicCity_ML
```

The number of vehicles comes from the SUMO route files; `numCars` in the ini has no effect.

Modify `simulations/scenarios/*/config.ini` to adjust:
- Vehicle density & routes
- Infrastructure positions & coverage
- RAT parameters (bandwidth, delay, power)
- Policy hysteresis & thresholds
- Handover decision interval

## Results & Analysis

Results saved per run:
```
results/<Scenario>_<Config>_<timestamp>/
├── run-settings.ini         Config snapshot
├── *.sca                    Statistics
├── *.vec                    Time-series vectors
└── analysis/
    ├── summary.csv          Aggregated KPIs
    └── plots/               Generated plots
```

Export & analyze:
```bash
python tools/analysis/export-results.py results/*/
python tools/analysis/plot-handovers.py results/*/
python tools/analysis/statistical-summary.py results/*/
```

## Contributing

See [CONTRIBUTING.md](.github/CONTRIBUTING.md) for guidelines.

## License

Research license — see [LICENSE](LICENSE)

## Citation

If you use MultiRATVANET in your research, please cite:

```
[Your citation here when published]
```

## Support

- **Issues:** GitHub Issues
- **Documentation:** See `docs/INDEX.md`
- **Troubleshooting:** See `docs/TROUBLESHOOTING.md`

---

**Built with:** OMNeT++ • INET • Veins • Simu5G • SUMO

**Maintained by:** [Your Team/Lab]

**Last Updated:** September 2026
