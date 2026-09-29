# MultiRATVANET Documentation Index

Welcome to the MultiRATVANET Framework documentation hub!

## Getting Started

- **[GETTING_STARTED.md](GETTING_STARTED.md)** — Installation, build, and first simulation run
- **[ARCHITECTURE.md](ARCHITECTURE.md)** — System design, components, and data flow

## Configuration & Usage

- **[CONFIGURATION.md](CONFIGURATION.md)** — All parameters and their meanings
- **[RAT_POLICIES.md](RAT_POLICIES.md)** — RAT selection strategies explained
- **[SCENARIO_SELECTION.md](SCENARIO_SELECTION.md)** — Choosing the right scenario for your research

## Tutorials (Step-by-Step Guides)

1. **[01-setup.md](tutorials/01-setup.md)** — Environment setup & verification
2. **[02-first-simulation.md](tutorials/02-first-simulation.md)** — Running your first scenario
3. **[03-custom-policy.md](tutorials/03-custom-policy.md)** — Writing a custom RAT selection policy
4. **[04-ml-integration.md](tutorials/04-ml-integration.md)** — Integrating machine learning agents
5. **[05-results-analysis.md](tutorials/05-results-analysis.md)** — Analyzing and visualizing results

## Scenario Guides

- **[HIGHWAY.md](scenarios/HIGHWAY.md)** — Baseline highway scenario (2 km, 70s)
- **[URBAN_GRID.md](scenarios/URBAN_GRID.md)** — Synthetic urban grid (2×2 km, 120s)
- **[ELECTRONIC_CITY.md](scenarios/ELECTRONIC_CITY.md)** — Real-world OSM Bangalore (1000s)

## API Reference

- **[MultiRatCar.md](api/MultiRatCar.md)** — Vehicle module API
- **[MultiRatAppManager.md](api/MultiRatAppManager.md)** — Manager module API
- **[Policies.md](api/Policies.md)** — RAT policy interface & implementations

## Technical Deep Dives

- **[V2V_COMMUNICATION.md](V2V_COMMUNICATION.md)** — CAM/DENM specification
- **[HANDOVER_MECHANICS.md](HANDOVER_MECHANICS.md)** — IP layer handover process
- **[FEDERATED_LEARNING.md](FEDERATED_LEARNING.md)** — FL integration guide
- **[METRICS_KPI.md](METRICS_KPI.md)** — Performance indicators and KPI collection

## Troubleshooting

- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** — Common issues and solutions

## Directory Structure

```
docs/
├── INDEX.md                    (this file)
├── GETTING_STARTED.md
├── ARCHITECTURE.md
├── CONFIGURATION.md
├── RAT_POLICIES.md
├── SCENARIO_SELECTION.md
├── V2V_COMMUNICATION.md
├── HANDOVER_MECHANICS.md
├── FEDERATED_LEARNING.md
├── METRICS_KPI.md
├── TROUBLESHOOTING.md
├── tutorials/                  (5 progressive guides)
├── scenarios/                  (per-scenario documentation)
├── api/                        (API references)
└── images/                     (diagrams & screenshots)
```

## Quick Commands

```bash
# Build framework
./tools/build.sh

# Run a scenario
./tools/run.sh Highway_CoveragePriority --sim-time-limit=70s

# Run with analysis
./tools/run.sh UrbanGrid_Ensemble --analyze

# Analyze existing results
python tools/analysis/export-results.py results/
python tools/analysis/plot-residency.py results/
```

## What to Read First

1. This file (INDEX.md) — Overview
2. [GETTING_STARTED.md](GETTING_STARTED.md) — Installation
3. [tutorials/02-first-simulation.md](tutorials/02-first-simulation.md) — First run
4. [ARCHITECTURE.md](ARCHITECTURE.md) — System design
5. [SCENARIO_SELECTION.md](SCENARIO_SELECTION.md) — Choose your use case

---

**Questions? See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) or check the API reference.**
