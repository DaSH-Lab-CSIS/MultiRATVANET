# MultiRATVANET Architecture

MultiRATVANET is a simulation testbed for comparing RAT selection policies on vehicles that carry
several radios at once. A car sends its traffic to a server over whichever radio access technology
(RAT) its policy has chosen, and the framework measures what that choice costs and delivers.

It runs on OMNeT++ 6.3 with INET 4.6 (802.11, IPv4), Simu5G 1.7 (5G-NR), Veins 5.3.1 and SUMO 1.22
(vehicle movement).

## The vehicle

`MultiRatCar` extends Simu5G's `NrCar` and adds two 802.11 station interfaces. Every RAT ends at
the same IPv4 stack, so switching RAT means changing the default route.

| RAT | Interface | Reaches the server through |
|---|---|---|
| DSRC (802.11, 5.9 GHz, 10 MHz) | `wlan[0]`, IP name `wlan0` | a `DsrcRsu` roadside unit |
| WiFi (802.11, 2.4 GHz, 20 MHz) | `wlan[1]`, IP name `wlan1` | a `WifiAp` access point |
| 5G-NR (Simu5G) | `cellularNic`, IP name `cellular` | a gNodeB and the UPF |
| LTE | (same `cellular` interface) | switched off: the networks have no eNodeB |
| 6G | `SixGInterface` placeholder | not equipped by default |

The RSUs sit on one switched LAN and the APs on another, each behind its own port of the core
router. The router has a route back to the cars' DSRC and WiFi addresses on those ports
(`simulations/router.mrt`), so the server's replies return over the RAT a request was sent on.

Two control modules sit in every car:

- **`RatCoverageMonitor`** publishes, every `updateInterval` (0.1 s), one `RatMetrics` record per
  RAT: in range, link up, SINR and its margin above the RAT's minimum, sensed load, link rate,
  and the round trip and loss of the car's probes.
- **`MultiRatAppManager`** asks the policy every `decisionInterval` (0.5 s) which RAT to use and
  moves the default route to it.

A network-wide **`RatStatsCollector`** samples how many cars are on each RAT, for the results.

## What the policies are given

A policy is given only what its own car knows: its position and speed, what it is connected
through, what its own radios observe, what its own probes find, and the replies to its own
traffic. It is told nothing about other cars, and nothing that only the infrastructure or the
server could know. With `signalSource = "measured"` (the default):

| Metric | 802.11 (DSRC, WiFi) | 5G-NR |
|---|---|---|
| signal | SNIR of frames from the associated RSU/AP, minus the transmit-power difference (the car sends uplink) | Simu5G downlink SINR of the serving cell, minus the power difference |
| load | channel busy ratio sensed by the car's radio | none: a car cannot see how loaded its cell is |
| link rate | rate the MAC sends data frames at | spectral efficiency from the car's SINR × cell bandwidth |
| probes | round-trip time and loss of the car's own probes, echoed by the server | same |
| in range | link up, signal measured within `measurementMaxAge`, SINR above the RAT's minimum (with hysteresis), and a probe echoed within `probeMaxAge` | same |

**Probing.** Every car runs a `MultiRatProbeApp`: every `probeInterval` (0.1 s) it sends a 50 B
packet over every RAT whose link is up, out of that RAT's own interface, and the server echoes
it. Nothing about latency is estimated; the round trip of the probes is the only latency figure.
Probing is the same for every policy and is real traffic on the channels.

`signalSource = "proxy"` is the older model for the radio figures: distance to the nearest
tower, a log-distance path-loss estimate, and fixed numbers per RAT. Policies cannot tell which
source is in use.

## Policies

One policy object belongs to one vehicle. On every decision the manager hands it a
`PolicyRequest` (the vehicle's id, position and speed, what it is connected through, the per-RAT
measurements and probe results, what became of the previous decision, and the replies each
traffic class received) and gets back a `PolicyResponse` naming the RAT to use: one default RAT,
and optionally a different RAT for a named traffic class. **[POLICY_REFERENCE.md](POLICY_REFERENCE.md)** lists every
field and shows how to write and plug in a policy.

The built-in policies share a base, `TimeToTriggerPolicy`:

- `prefer(current, metrics)`: the RAT it would use right now. It returns the current RAT unless
  another one is better by the policy's own margin. It never returns a RAT that is out of range.
- The base turns a preference into a switch only after the same different RAT has been preferred
  for `timeToTrigger` (1 s). If the current RAT is lost, the preferred RAT is taken at once.

| Policy | Prefers | Margin before it prefers another RAT |
|---|---|---|
| `CoveragePriority` | the first in-range RAT in the order DSRC, WiFi, NR, LTE, 6G | only a higher-priority RAT |
| `Sinr` | the largest SINR margin (SINR above the RAT's minimum) | `sinrSwitchMargin` (3 dB) |
| `LatencyQos` | the highest link rate among RATs whose probes come back within `latencyBudget` (100 ms one way, half the round trip); if none, the lowest latency | 25 % more link rate |
| `Load` | the lowest sensed load among DSRC and WiFi; cellular only when neither is usable | `loadSwitchMargin` (0.15) |
| `Ensemble` | the RAT with the most weighted votes of the four policies above | the leader must beat the current RAT by more than `ensembleStickiness` votes |
| `Ml` | the RAT last passed to `MlPolicy::suggest()` if it is in range; otherwise as CoveragePriority | — |

`Ensemble` asks each member for its preference on every decision and applies the time-to-trigger
once, to the outcome of the vote. `ensembleWeightCoverage/Sinr/Latency/Load` set the vote weights
(0 disables a voter).

`Ml` is a hook. Nothing in this repository calls `suggest()`, so on its own it decides like
CoveragePriority.

`OnlyDsrc`, `OnlyWifi` and `OnlyNr` are baselines, not policies: the car uses that one RAT and
nothing else. The test bench (`bench/run.sh`, [bench/README.md](../bench/README.md)) runs the five
policies other than `Ml` and the three baselines with the same seeds and compares them.

The built-in policies put every traffic class on the same RAT. `ExampleSplit` is a template that
shows the standard interface used directly and a RAT per class (safety on DSRC/WiFi,
infotainment on NR); it is not one of the policies being compared.

## The switch

1. Decision timer fires; the manager builds the request from the monitor's metrics and the
   vehicle's own state.
2. The policy returns a default RAT and, if it wants, a RAT for a traffic class. The manager
   applies the answer and adds nothing of its own: no waiting and no smoothing.
3. Default RAT: if it differs from the current one and is in range, the manager replaces the IPv4
   default route. A scenario can set an extra switch delay (`handoverExecDelay`, or
   `<rat>HandoverDelay` per target RAT; 0 s by default) for signalling the simulators do not model.
4. A class with a RAT of its own is sent out of that RAT's interface from its next packet on.
5. What the switch really costs (packets queued on the old link, the new link's first-packet
   delay) comes out of the simulated stacks and is measured at the server.

A switch back to the previous RAT within `pingPongWindow` (2 s) counts as a ping-pong.

## Traffic and what is measured

Traffic is request-and-reply. Each car runs two `MultiRatTrafficApp`s and a `MultiRatProbeApp`;
the server runs one `MultiRatSink` for each. The server answers every request over the RAT it
came in on.

| Class | The car sends | The server answers | Judged |
|---|---|---|---|
| safety | 200 B every 100 ms | one 50 B acknowledgement | at the server: there within 100 ms |
| infotainment | a 50 B request every 100 ms in on/off bursts (about 2 s on, 3 s off) | ten 1250 B data packets, 10 ms apart (1 Mbit/s) | at the car: each data packet there within 1 s of its request |
| probe | 50 B on every linked RAT every 100 ms | a 50 B echo | not judged; feeds the policy |

| Where | Scalars |
|---|---|
| `car[*].multiRatAppManager` | `handoversTotal`, `pingPongTotal`, `pingPongRatio`, `<RAT>.selectionShare`, `<RAT>.residencyTime` (default RAT); `<class>.switches`, `<class>.<RAT>.selectionShare` (per traffic class); `handoverFailed:count`, `decisionRejected:count`, `handoverDelayMean/Max/Total` (the configured extra delay) |
| `car[*].ratCoverageMonitor` | `connectivityRatio`, `outageRatio`, `outageCount`, `maxOutageDuration`, `multiConnectivityRatio`, `<rat>InRange:timeavg`, `<RAT>.inRangeSinrMargin/Load/LinkRate/ProbeRtt` |
| `car[*].app[0..1]` | `packetSent:count`, `<RAT>.packetsSent`, `repliesExpected`, `repliesReceived`, `repliesWithinDeadline`, `replyDelay` |
| `car[*].app[2]` | `<RAT>.probesSent`, `<RAT>.probesEchoed`, `<RAT>.probeRttMean` |
| `server.app[k]` | `packetsReceived`, `packetsWithinDeadline`, `<RAT>.packetsReceived`, `repliesSent`, `endToEndDelay`, `switchInterruption` (first request sent on the new RAT until the first one that arrives), `switchLoss` |
| `ratStatsCollector` | `vehicles<Rat>` over time, positions of the infrastructure |

`V2vBeaconApp` (config `V2V`) broadcasts beacons car to car over a third, ad-hoc DSRC interface
and records neighbours, reception ratio, delay and channel busy ratio. Config `CV2X` does the same
over the NR sidelink with Simu5G's alert apps.

## Scenarios

| Scenario | Network | Vehicles | Infrastructure | Configs |
|---|---|---|---|---|
| Highway | `MultiRatHighway`, 2 km straight road | 17 | 3 RSUs, 2 APs, 2 gNodeBs | one per policy, `EnsembleSweep`, `DsrcNrHandover`, `V2V`, `CV2X` |
| Urban grid | `MultiRatUrbanGrid`, 5×5 blocks | 40 | 10 RSUs, 10 APs, 2 gNodeBs | `UrbanGrid_*` |
| ElectronicCity | `ElectronicCity`, OpenStreetMap of Bangalore | 968 over 1000 s | 15 RSUs, 15 APs, 3 gNodeBs | `ElectronicCity_*` |

The number of vehicles comes from the SUMO route file of the scenario
(`simulations/scenarios/<scenario>/*.rou.xml`). The networks extend Simu5G's NR `Highway` network,
which provides the gNodeBs, UPF, router and server.

## Extending

**A new policy**

See [POLICY_REFERENCE.md](POLICY_REFERENCE.md): implement `decide()` and `name()` on
`IRatSelectionPolicy` (or `prefer()` on `TimeToTriggerPolicy`), register the name in
`RatPolicyFactory::create()`, and set `*.car[*].multiRatAppManager.policy`.

**A new scenario**

1. Put the SUMO network, routes, `.sumocfg` and `.launchd.xml` in `simulations/scenarios/<name>/`.
2. Add a network in `simulations/networks/` (extend `MultiRatHighway` and set the number of APs
   and RSUs).
3. Add a base config in `omnetpp.ini` with the launch file and the infrastructure positions. Set
   `mobility.initFromDisplayString = false` on every node you position, or the coordinates are
   ignored. Positions are in the OMNeT++ frame: check them against where the cars drive
   (`selfXmin/selfXmax/selfYmin/selfYmax` in a result file).

**An external controller for `Ml`**

`MlPolicy::suggest(RatId)` is the entry point. The manager does not yet expose it: a controller
module needs a public method on `MultiRatAppManager` that forwards to the policy.
