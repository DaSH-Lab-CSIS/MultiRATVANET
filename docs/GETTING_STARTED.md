# Getting Started

There are two ways to build and run: with Docker (recommended; nothing else to install) or on a
toolchain you built yourself.

## With Docker

Needs Docker 20.10+ and this repository.

```bash
# 1. Build the image. The first build compiles OMNeT++, INET, Veins, Simu5G and SUMO: 1-2 h.
dash/build-image.sh

# 2. Run one config for 120 simulated seconds. Results go to ./results
dash/mrv run Sinr --sim-time-limit=120s

# 3. Or run an experiment with parameters and get an HTML report (results/report.html)
dash/run-experiment.sh --scenario highway --policy ensemble --time 120s --ensemble-weight-sinr 2
dash/run-experiment.sh --help
```

Put `DOCKER="sudo docker"` in front of a command if your user is not in the `docker` group.
The image starts its own TraCI launch daemon, so there is nothing else to start.

## Without Docker

Build these first; the versions must match:

| Software | Version | Notes |
|---|---|---|
| OMNeT++ | 6.3.0 | |
| INET | 4.6.0 | apply `docker/base/patches/inet-4.6.0-dash.patch` |
| Veins | 5.3.1 | with `subprojects/veins_inet` |
| Simu5G | 1.7.0 | apply `docker/base/patches/simu5g-1.7.0-dash.patch`; without it the cellular path delivers nothing |
| SUMO | 1.22.0 | Veins 5.3.1 does not support newer TraCI versions |

`docker/base/Dockerfile` is the exact recipe if you want to follow it by hand.

Tell the scripts where they are (the defaults in the scripts are the paths on the lab server):

```bash
export OMNETPP_BIN=/path/to/omnetpp-6.3.0/bin
export INET_DIR=/path/to/inet-4.6.0
export VEINS_DIR=/path/to/veins-5.3.1
export SIMU5G_DIR=/path/to/simu5g-1.7.0
```

If OMNeT++ was installed with `opp_env`, run the commands below inside an `opp_env shell`.

```bash
# 1. Build the framework (output: framework/out/clang-release/framework)
./tools/build.sh

# 2. In a second terminal: start the TraCI launch daemon and leave it running (port 9999)
./tools/sumo-launchd.sh

# 3. Run a config
./tools/run.sh Sinr --sim-time-limit=120s
```

`./tools/run.sh` without arguments lists the configs. Without `--sim-time-limit` a run lasts as
long as the config says in `simulations/omnetpp.ini` (300 s highway, 120 s urban grid, 1000 s
ElectronicCity). Any other `--<ini-key>=<value>` is passed to the simulation, for example
`'--*.car[*].multiRatAppManager.timeToTrigger=2s'`.

## Results

Each run gets its own folder, `results/<CONFIG>_<timestamp>/` (under `$RESULTS_ROOT` if set):

- `*.sca`: scalars. Per car: `handoversTotal`, `pingPongTotal`, `<RAT>.selectionShare`,
  `connectivityRatio`, `outageRatio`, and per traffic class `repliesExpected` /
  `repliesReceived`. Per traffic class at the server: `packetsReceived`,
  `packetsWithinDeadline`, `endToEndDelay`, `switchInterruption`.
- `*.vec`, `*.vci`: time series.
- `run-settings.ini`: a copy of `omnetpp.ini` as it was run.

`python3 dash/report.py results` builds `results/report.html` from every run under `results/`.

## Troubleshooting

| Symptom | Cause |
|---|---|
| The run stops at start with a TraCI connection error | No launch daemon on port 9999. Start `tools/sumo-launchd.sh`, or check that another user's daemon is not holding the port. |
| `This OMNeT++ installation cannot be used outside an opp_env shell` | Run `tools/build.sh` inside `opp_env shell`. |
| The server receives nothing over cellular | Simu5G was built without `simu5g-1.7.0-dash.patch`. |
| `Unknown policy "..."` | The `policy` parameter is not one of CoveragePriority, Sinr, LatencyQos, Load, Ml, Ensemble. |
| The image build fails downloading sources | Put the release tarballs in `docker/base/dl/`; see `docker/base/README.md`. |
