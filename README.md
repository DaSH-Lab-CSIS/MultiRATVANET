# MultiRATVANET Framework

**Multi-RAT VANET Handover Simulation Framework** for OMNeT++ / Veins / SUMO / INET / Simu5G

A vehicle carries multiple radio access technologies (DSRC, WiFi, LTE, 5G-NR) simultaneously, all terminating at a unified IPv4 stack. An application-layer RAT selector orchestrates handovers based on configurable policies, enabling research into multi-RAT vehicular network optimization.

## Quick Start

```bash
# Build
./tools/build.sh

# Run a scenario
./tools/run.sh Highway_CoveragePriority --sim-time-limit=70s

# Analyze results
python tools/analysis/plot-residency.py results/
```

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

- **OMNeT++ 5.6.1** (built)
- **INET 4.2.2** (built)
- **Veins 5.2** + veins_inet (built)
- **Simu5G 1.1.0** (built)
- **SUMO 1.24+** (on PATH)
- **Python 3.8+** (for analysis tools)

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

```bash
# Compile framework
cd framework
opp_makemake -f --deep -O out -L [framework_paths]
make -j4

# Run scenario
cd ..
./tools/run.sh UrbanGrid_Ensemble --sim-time-limit=120s

# Analyze results
python tools/analysis/export-results.py results/
python tools/analysis/plot-metrics.py results/
```

## Configuration

Each scenario has multiple configurations:

```
Highway_CoveragePriority      Fixed priority (DSRC > WiFi > NR > LTE)
Highway_Ensemble              Multi-objective voting
Highway_ML                    ML agent hook
UrbanGrid_*                   Similar variants
ElectronicCity_*              Real-world scenario
```

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
