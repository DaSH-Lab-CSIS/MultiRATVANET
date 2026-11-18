# MultiRATVANET Documentation

- **[GETTING_STARTED.md](GETTING_STARTED.md)** — build and first run, with Docker or on your own toolchain; troubleshooting
- **[POLICY_REFERENCE.md](POLICY_REFERENCE.md)** — writing a policy: every input the simulator provides, the response format, a complete example, how to plug it in
- **[ARCHITECTURE.md](ARCHITECTURE.md)** — what each module does, the RAT selection policies and their parameters, the metrics, the scenarios, and how to add a policy or a scenario
- **[../bench/README.md](../bench/README.md)** — the test bench: every policy against the one-RAT baselines, to rerun after any change to the harness
- **[../README.md](../README.md)** — overview, command reference, list of configs
- **[../docker/base/README.md](../docker/base/README.md)** — the pinned toolchain image and the INET / Simu5G patches
- **[../dash/manifest.yaml](../dash/manifest.yaml)** — scenarios, algorithms, parameters and metrics as the dashboard sees them

Where things are set:

| What | Where |
|---|---|
| Configs, infrastructure positions, traffic, policy settings | `simulations/omnetpp.ini` |
| Module parameters and their defaults | `framework/src/multirat/*/*.ned` |
| Number of vehicles and their routes | `simulations/scenarios/<scenario>/*.rou.xml` |
| Network topology | `simulations/networks/*.ned` |
