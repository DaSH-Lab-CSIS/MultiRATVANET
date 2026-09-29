# MultiRATVANET System Architecture

## Overview

MultiRATVANET is a simulation framework for multi-RAT (DSRC, WiFi, LTE, 5G-NR, 6G) vehicular handover research. Vehicles carry multiple radios simultaneously, all terminating at a unified IPv4 stack. An application-layer manager selects the active RAT and performs handovers by swapping the default route.

## System Layers

```
┌─────────────────────────────────────────┐
│   Application Layer (OMNeT++ Apps)      │  V2V/V2X CAM/DENM
│   - V2vBeaconApp (CAM broadcast)        │
│   - V2nDataApp (V2N traffic)            │
│   - V2xAlertApp (emergency alerts)      │
└─────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────┐
│   RAT Manager Layer (MultiRatAppManager)│  Policy-driven handover
│   - Handover decision logic             │
│   - Route swapping (IPv4)               │
│   - Handover statistics (KPIs)          │
└─────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────┐
│   Policy Layer (IRatSelectionPolicy)    │  Pluggable policies
│   - CoveragePriority                    │
│   - SinrBased                           │
│   - LatencyQos                          │
│   - LoadBalanced                        │
│   - EnsembleVoting                      │
│   - MlAgent                             │
└─────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────┐
│   Monitor Layer (Coverage/SINR/Latency) │  Per-RAT metrics
│   - RatCoverageMonitor (in-range check) │
│   - RatSignalMonitor (SINR, SNR)       │
│   - RatLatencyMonitor (delay)           │
└─────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────┐
│   MAC/PHY Layer (Simu5G + INET)         │  Radio simulation
│   - LTE/NR cells (Simu5G gNodeBs)       │
│   - WiFi APs (INET)                     │
│   - DSRC RSUs (INET)                    │
│   - 6G placeholder                      │
└─────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────┐
│   Traffic Simulation (Veins + SUMO)     │  Vehicular movement
│   - Vehicle mobility & positioning      │
│   - Road network (SUMO)                 │
│   - TraCI connection                    │
└─────────────────────────────────────────┘
```

## Module Hierarchy

### Vehicle (MultiRatCar extends Simu5G NRCar)

```
MultiRatCar
├── cellularNic                  LTE/5G-NR (Simu5G)
├── wlan[0]                      DSRC @ 5.9 GHz (INET 802.11p)
├── wlan[1]                      WiFi @ 2.4 GHz (INET)
├── ipv4                         Unified IPv4 stack
├── ipv4.arp
├── ipv4.icmp
├── networkLayer.ipv4Routing    Routing protocol (AODV or default)
│
├── ratCoverageMonitor           → Monitors all RATs in-range
├── multiRatAppManager           → Selects active RAT
│   └── policy                   → Selection strategy
│       └── metrics              → Coverage, SINR, latency
│
└── app[]                        Applications
    ├── V2vBeaconApp             CAM/DENM generator
    ├── V2nDataApp               V2N traffic
    └── [other apps]
```

### Infrastructure

```
MultiRatHighway (extends Simu5G Highway)
├── gNodeB[0], gNodeB[1]         5G-NR cells (Simu5G)
├── upf                          User Plane Function (Simu5G)
├── router                       Core router
├── server                       Content server
│
├── wifiAp[0..9]                 WiFi access points (INET)
├── dsrcRsu[0..9]                DSRC roadside units (INET)
│
├── dsrcMedium                   DSRC radio medium (5.9 GHz)
└── wifiMedium                   WiFi radio medium (2.4 GHz)
```

## Data Flow

### Packet Flow (Inbound)

```
1. Radio Reception
   Radio Medium → MAC Layer (802.11p, 802.11a/g, LTE, NR)
                        ↓
2. MAC-to-IP
   MAC Layer → NIC Interface (wlan[0], wlan[1], cellularNic)
                        ↓
3. Active Route
   [Active RAT Interface] → IPv4 Routing → IPv4 Stack
                        ↓
4. Application Delivery
   IPv4 Stack → Socket → Application (V2vBeaconApp, etc.)
                        ↓
5. Statistics
   RatStatsCollector records delivery latency, packet loss
```

### Handover Flow

```
1. Monitor Phase (every 0.1s)
   RatCoverageMonitor.check() {
       for each RAT:
           measure RSSI, SNR, latency, load
   }
                        ↓
2. Decision Phase (every 0.3s, configurable)
   MultiRatAppManager.decide() {
       policy.selectRat(metrics) → RatId newRat
       if newRat != currentRat:
           route_switch(newRat)
   }
                        ↓
3. Route Swap Phase
   IPv4.setDefaultRoute(newRat.interface)
   MultiRatAppManager.recordHandover()
                        ↓
4. Statistics
   RatStatsCollector.handover++ (count)
   RatStatsCollector.handoverLatency (latency)
```

## RAT Selection Policies

### CoveragePriority
- Fixed priority: DSRC > WiFi > NR > LTE
- Selects highest-priority in-range RAT
- **Advantage:** Predictable, baseline reference
- **Disadvantage:** Ignores quality, may cause ping-pong

### SinrBased
- Selects RAT with highest SINR
- Hysteresis to reduce ping-pong
- **Advantage:** Quality-aware
- **Disadvantage:** May ignore coverage gaps

### LatencyQos
- Minimizes end-to-end latency
- Suitable for real-time applications
- **Advantage:** Low latency
- **Disadvantage:** Ignores throughput/coverage

### LoadBalanced
- Distributes traffic across available RATs
- Reduces congestion
- **Advantage:** Better aggregate throughput
- **Disadvantage:** May sacrifice individual flow quality

### EnsembleVoting
- Weighted multi-objective voting:
  - Coverage (1.0) — is RAT in range?
  - SINR (1.5) — signal quality
  - Latency (1.5) — delay
  - Load (1.0) — congestion
- Hysteresis (configurable 2.0-3.0x)
- **Advantage:** Balanced, realistic
- **Disadvantage:** Requires tuning

### MlAgent
- Placeholder for ML/FL-driven selection
- External agent (e.g., DQN, PPO) can be connected
- **Advantage:** Learns optimal policy
- **Disadvantage:** Requires training data

## Statistics Collection

### Per-Vehicle KPIs

| Metric | Unit | Collected By | Usage |
|--------|------|---|---|
| Handover Count | # | RatStatsCollector | Mobility indicator |
| Handover Latency | ms | RatStatsCollector | Disruption cost |
| Ping-Pong Ratio | % | RatStatsCollector | Policy stability |
| RAT Residency | % | RatCoverageMonitor | RAT utilization |
| RSSI | dBm | RatCoverageMonitor | Link quality |
| SNR | dB | RatSignalMonitor | Signal quality |
| V2V Packet Loss | % | V2vBeaconApp | Reliability |
| V2V Latency | ms | V2vBeaconApp | End-to-end delay |

### Exported to .sca Files
```
car[0].multiRatAppManager.handoverCount:sum = 15
car[0].multiRatAppManager.avgHandoverLatency:mean = 65.4
car[0].ratStatsCollector.dsrcResidency = 0.25
car[0].v2vBeaconApp.sentMsg:sum = 700
car[0].v2vBeaconApp.rcvdMsg:sum = 685
```

## Scenarios

### Highway (Baseline)
- 2 km linear road
- 7-10 vehicles
- 2 gNodeBs, 2 WiFi APs, 3 DSRC RSUs
- Duration: 70 seconds
- Use case: Baseline performance reference

### UrbanGrid (Synthetic Urban)
- 2×2 km grid (5×5 intersections)
- 40-60 vehicles
- 1 gNodeB, 10 WiFi APs, 10 DSRC RSUs
- Duration: 120 seconds
- Use case: Dense handover testing, ML training

### ElectronicCity (Real-World OSM)
- 5×5 km Bangalore, India (real OpenStreetMap)
- 50-80 vehicles
- 3 gNodeBs, 15 WiFi APs, 15 DSRC RSUs
- Duration: 1000 seconds
- Use case: Realistic validation, long-term FL convergence

## Configuration

### Key Parameters (omnetpp.ini)

```ini
[General]
network = MultiRatHighway
sim-time-limit = 70s
repeat = 1

[Config Highway_Base]
*.car[*].multiRatAppManager.policy = "CoveragePriority"
*.car[*].multiRatAppManager.decisionInterval = 0.3s

[Config Highway_Ensemble]
*.car[*].multiRatAppManager.policy = "EnsembleVoting"
*.car[*].multiRatAppManager.ensembleWeights = "1.0, 1.5, 1.5, 1.0"
*.car[*].multiRatAppManager.hysteresisThreshold = 2.0
```

## Extension Points

### Adding a New RAT
1. Define in RatTypes.h (enum RatId)
2. Create NIC module (e.g., MmWaveNic.ned)
3. Add to MultiRatCar.ned as new module
4. Create monitor (e.g., RatMmWaveMonitor.cc)
5. Update all policies to handle new RAT

### Adding a New Policy
1. Inherit from IRatSelectionPolicy
2. Implement selectRat() method
3. Register in RatPolicyFactory.cc
4. Add to omnetpp.ini

### Adding a New Scenario
1. Create SUMO network (.net.xml) + routes (.rou.xml)
2. Create NED topology (MultiRatScenario.ned)
3. Add [Config Scenario_*] in omnetpp.ini
4. Document in docs/scenarios/SCENARIO.md

---

For detailed API, see [docs/api/](../api/).
For tutorials, see [docs/tutorials/](../tutorials/).
