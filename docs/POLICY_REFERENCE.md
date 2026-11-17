# Policy Reference

How to write a RAT selection policy for MultiRATVANET: what the simulator gives a policy, what a
policy gives back, and how to plug one in.

**The rule for inputs.** A car is an independent unit. Its policy is given only what that car
knows by itself: its own position and speed, what it is connected through, what its own radios
measure or sense, what its own probes find, and the replies it gets to its own traffic. It is
given nothing about other cars, and nothing that only the infrastructure or the server could
know (how loaded a cell is, whether a packet arrived that was never answered).

**The rule for the harness.** The simulator applies the policy's answer as given. It does not
wait, smooth or second-guess. Guarding against flip-flopping is the policy's job.

The types are in `framework/src/multirat/base/PolicyTypes.h` and `RatTypes.h`; the interface is in
`framework/src/multirat/policies/IRatSelectionPolicy.h`. None of them depend on OMNeT++, so a
policy can be compiled and unit-tested on its own.

## The contract

```cpp
class IRatSelectionPolicy {
  public:
    virtual PolicyResponse decide(const PolicyRequest &request) = 0;   // required
    virtual const char *name() const = 0;                              // required
    virtual void vehicleLeft(const PolicyRequest &last) {}             // optional
};
```

- **One policy object per vehicle.** It is created when the vehicle appears and destroyed when
  it leaves. Member variables are that vehicle's private memory.
- **`decide()` is called once per decision interval** (`decisionInterval`, 0.5 s by default),
  starting `startTime` after the vehicle appears, at a random phase so vehicles do not decide in
  lockstep. The request describes that one vehicle at that moment.
- **The answer is a RAT for each traffic class** of the vehicle: one default RAT, and optionally
  a different RAT for a named class.
- **`vehicleLeft()`** is called once, when the vehicle leaves or the run ends, with the vehicle's
  final state. A learning policy uses it to close an episode.

**Time.** The simulator waits for `decide()` to return, and simulated time does not advance while
it waits. A slow policy makes the run take longer on the clock but does not change any result.

**Determinism.** A policy that uses random numbers should seed them itself, from
`request.vehicle.id` for example, so a run can be repeated.

## How the car learns things

Besides what its radios measure, a car learns about its RATs in two ways. Both are real traffic
in the simulation.

- **Probes.** Every 0.1 s (`probeInterval`) the car sends a small packet over every RAT whose
  link is up, and the server echoes it. From the echoes the car knows each RAT's round-trip time
  and how many probes were lost. Probing is part of the harness: it is the same for every
  policy, and a policy cannot change it or turn it off.
- **Replies to its own traffic.** Traffic is request-and-reply, and the server always answers
  over the RAT the request came in on.

| Traffic class | The car sends | The server answers | Judged |
|---|---|---|---|
| `safety` | a 200 B message every 100 ms | one 50 B acknowledgement | at the server: message there within 100 ms |
| `infotainment` | a 50 B request every 100 ms, in bursts (about 2 s on, 3 s off) | ten 1250 B data packets, 10 ms apart | at the car: each data packet there within 1 s of its request |

## Request

`PolicyRequest` is what the vehicle knows at the decision.

| Field | Type | Meaning |
|---|---|---|
| `sequence` | `long` | Number of this request for this vehicle, from 0. |
| `time` | `double` s | Simulation time. |
| `decisionInterval` | `double` s | Configured time between requests. |
| `vehicle` | `VehicleState` | Who is asking and where it is. |
| `connection` | `ConnectionState` | Its default RAT and switching history. |
| `rats` | `std::vector<RatMetrics>` | One entry per RAT, indexed by `ratIndex(RatId)`. |
| `previous` | `PreviousDecision` | What became of the previous answer. |
| `traffic` | `std::vector<TrafficState>` | One entry per traffic class: its RAT and the replies received. |

### `RatId`

`DSRC = 0`, `WIFI = 1`, `LTE = 2`, `NR = 3`, `SIXG = 4`, `NONE = -1`; `COUNT = 5`.
`ratIndex(r)` gives the index into `rats`; `ratName(r)` gives a printable name.
In the shipped scenarios LTE and 6G are not equipped (`present == false`).

### `VehicleState`

| Field | Type | Meaning |
|---|---|---|
| `id` | `int` | Unique per run, never reused: the index of the car in the simulation (`car[id]`). |
| `externalId` | `std::string` | The vehicle's id in SUMO. Empty if the vehicle is not driven by SUMO. |
| `x`, `y`, `z` | `double` m | Position in the simulation frame (y grows downward relative to SUMO). |
| `vx`, `vy` | `double` m/s | Velocity. |
| `speed` | `double` m/s | |
| `heading` | `double` rad | `atan2(vy, vx)`; 0 when standing still. |

Position and velocity are the values SUMO last reported (every 0.1 s).

### `ConnectionState`

About the vehicle's **default RAT**: the one named by `PolicyResponse::rat`, used by every
traffic class the policy did not put elsewhere.

| Field | Type | Meaning |
|---|---|---|
| `currentRat` | `RatId` | The default RAT. `NONE` before the first attach. |
| `previousRat` | `RatId` | Default RAT before the current one. |
| `timeOnCurrentRat` | `double` s | Time since the current default RAT became active. |
| `switchCount` | `long` | Completed switches of the default RAT so far. |
| `pingPongCount` | `long` | Of those, returns to the previous RAT within `pingPongWindow` (2 s). |
| `switchInProgress` | `bool` | A switch has started and not finished. Only happens when a scenario sets an extra switch delay. A different default RAT returned now is ignored. |
| `pendingRat` | `RatId` | Its target; `NONE` otherwise. |

Note that `currentRat` can be out of range: the vehicle stays on a lost RAT until a policy names
another one.

### `RatMetrics` (one per RAT)

What the car knows about each RAT. The third column says how the value is obtained:
**measured** is read from the car's simulated radio, **sensed** is the radio listening to its
channel, **probed** comes from the echoes of the car's probes, **derived** is computed from the
car's own measurements, **configured** is a property of the radio.

| Field | Type | Source | Meaning |
|---|---|---|---|
| `id` | `RatId` | | Which RAT this entry is. |
| `present` | `bool` | configured | The vehicle has this RAT (`has<Rat>` on the coverage monitor). |
| `inRange` | `bool` | derived | Usable now. This is the harness's one rule for "usable": link up, signal measured within `measurementMaxAge` (0.5 s), `sinrDb >= minSinrDb` (plus 2 dB to enter), **and a probe echoed by the server over this RAT within `probeMaxAge` (0.5 s)**. **A policy may only return RATs with `present && inRange`.** |
| `linked` | `bool` | measured | DSRC/WiFi: associated with an RSU/AP. NR: attached to a serving cell. Probes are sent on every linked RAT. |
| `sinrDb` | `double` dB | measured | Uplink SINR estimate, smoothed. DSRC/WiFi: SNIR of frames from the associated RSU/AP. NR: Simu5G downlink SINR of the serving cell. Both minus the transmit-power difference between infrastructure and car, since the car is the one sending. `-50` when there is no recent measurement. |
| `minSinrDb` | `double` dB | configured | Lowest SINR the RAT can use (DSRC/WiFi 10, NR −5). `sinrDb − minSinrDb` is the margin, which is comparable across RATs; raw SINR is not. |
| `rssiDbm` | `double` dBm | measured | DSRC/WiFi: received power of the strongest RSU/AP frame in the last 0.1 s. `NaN` for NR (Simu5G reports SINR, not power) and when there is no recent measurement. |
| `load` | `double` 0..1 | sensed | DSRC/WiFi: channel busy ratio, the share of time the car's radio heard the channel in use (or was sending), smoothed. **`NaN` for NR**: a car cannot see how loaded its cell is. Test with `std::isnan()`. |
| `linkRateMbps` | `double` Mbit/s | measured / derived | Rate the radio would send at with the channel to itself. DSRC/WiFi: the rate the MAC sends data frames at. NR: spectral efficiency from `sinrDb` (capped at 5.55 bit/s/Hz) × cell bandwidth. 0 when there is no recent measurement. |
| `probeRttMs` | `double` ms | probed | Round-trip time of the latest probe echoed over this RAT. `NaN` if none yet. |
| `probeRttMeanMs` | `double` ms | probed | Mean round trip of the probes of the last second. `NaN` if none was echoed. |
| `probeLoss` | `double` 0..1 | probed | Share of recent probes that were not echoed (a probe counts as lost after 0.5 s). `NaN` if none was sent. |
| `probeAge` | `double` s | probed | Time since the latest echo; `-1` if never. |
| `measurementAge` | `double` s | measured | Time since the signal was last measured; `-1` if never. |
| `lastUpdate` | `double` s | | Simulation time these metrics were refreshed (every 0.1 s). |

There is no latency estimate and no capacity figure. The only latency a car knows is what its
probes and replies show.

`IRatSelectionPolicy::usable(rat, request.rats)` tests `present && inRange`;
`candidates(request.rats)` lists the RATs that pass.

With `signalSource = "proxy"` the radio fields are filled from a distance-based estimate and
fixed per-RAT numbers instead. A policy cannot tell the difference and should not need to.

### `PreviousDecision`

About the default RAT.

| Field | Type | Meaning |
|---|---|---|
| `requestedRat` | `RatId` | The default RAT the policy returned last time. |
| `outcome` | `DecisionOutcome` | What the simulator did with it. |

| `DecisionOutcome` | Meaning |
|---|---|
| `NONE` | There was no previous request. |
| `KEPT` | The answer was the current RAT or `NONE`; nothing changed. |
| `ATTACHED` | First RAT of this vehicle taken into use. |
| `SWITCH_COMPLETED` | The vehicle moved to the requested RAT. |
| `SWITCH_PENDING` | The switch started and is still waiting out the extra switch delay. |
| `SWITCH_FAILED` | The requested RAT could not be taken into use (left coverage during the delay, or no interface). |
| `REJECTED` | The requested RAT was not in range; nothing was done. Counted in `decisionRejected`. |
| `IGNORED` | A switch was already in progress; nothing was done. |

### `TrafficState` (one per traffic class)

What the car has seen of each of its traffic classes.

| Field | Type | Meaning |
|---|---|---|
| `trafficClass` | `std::string` | Name of the class: `"safety"`, `"infotainment"`. |
| `rat` | `RatId` | RAT the class is sent on now. |
| `switchCount` | `long` | Times the class has changed RAT. |
| `window` | `TrafficCounters` | Since the previous request to the policy. |
| `total` | `TrafficCounters` | Since the vehicle appeared. |

| `TrafficCounters` | Type | Meaning |
|---|---|---|
| `requests` | `long` | Requests the car sent (safety messages, infotainment chunk requests). |
| `repliesExpected` | `long` | Reply packets those requests asked for (1 per safety message, 10 per infotainment request). |
| `repliesReceived` | `long` | Reply packets that arrived. |
| `delaySum` | `double` s | Sum, over the received replies, of the time from sending the request to the reply arriving; mean = `delaySum / repliesReceived`. |
| `delayMax` | `double` s | |

A reply counts in the window it arrives in, which can be the one after its request was sent, so
`window.repliesReceived` can exceed `window.repliesExpected`. Use the `total` counters for loss.

## Response

```cpp
struct PolicyResponse {
    RatId rat;                               // the default RAT
    std::map<std::string, RatId> classRat;   // optional: a different RAT for a class
    std::string reason;                      // optional, written to the simulation log
};
```

`PolicyResponse(RatId)` puts every class on one RAT, which is what the built-in policies do.

**`rat`, the default RAT**

| `rat` | What the simulator does |
|---|---|
| `NONE`, or the current default RAT | Nothing. The vehicle stays where it is. |
| A different RAT that is `present && inRange` | Switches to it: moves the default route (after the extra switch delay, if a scenario sets one). With no current RAT it attaches at once. |
| A different RAT that is not in range | Nothing. The next request says `REJECTED`. |
| Anything, while `switchInProgress` | Nothing. The next request says `IGNORED`. |

**`classRat`, per traffic class**

| Entry for a class | What the simulator does |
|---|---|
| none, or `NONE` | The class uses the default RAT. |
| A RAT that is `present && inRange` | The class is sent out of that RAT's interface from the next packet on, and its replies come back the same way. No switch delay applies. |
| A RAT that is not in range | The class uses the default RAT. Counted in `decisionRejected`. |

The entry has to be given again on every decision: a class with no entry goes back to the
default RAT. `request.traffic[i].rat` shows where each class is now.

## A complete policy

`framework/src/multirat/policies/ExampleSplitPolicy.h` is a working policy written directly
against the request and response, registered as `ExampleSplit`. It is a template, not one of the
policies being compared. It sends safety over a short-range RAT (DSRC or WiFi) and infotainment
over 5G-NR, and moves a class only after the same different RAT has been its choice for a
second. Its core:

```cpp
PolicyResponse decide(const PolicyRequest &req) override {
    // short-range RAT for safety: keep the one in use while it works; when choosing anew,
    // DSRC or WiFi, whichever answers probes faster
    RatId current = req.connection.currentRat;
    RatId shortRange = RatId::NONE;
    if ((current == RatId::DSRC || current == RatId::WIFI) && usable(current, req.rats))
        shortRange = current;
    else {
        double bestRtt = 1e18;
        for (RatId r : { RatId::DSRC, RatId::WIFI }) {
            const RatMetrics &m = req.rats[ratIndex(r)];
            if (m.present && m.inRange && !std::isnan(m.probeRttMeanMs) && m.probeRttMeanMs < bestRtt) {
                bestRtt = m.probeRttMeanMs;
                shortRange = r;
            }
        }
    }
    const RatMetrics &nr = req.rats[ratIndex(RatId::NR)];
    bool nrGood = nr.present && nr.inRange && !(nr.probeLoss > 0.2);

    RatId wantSafety = shortRange != RatId::NONE ? shortRange : (nrGood ? RatId::NR : firstUsable(req));
    RatId wantInfotainment = nrGood ? RatId::NR : wantSafety;

    // move a class only once the same choice has held (settle() is the policy's own timer)
    PolicyResponse resp;
    resp.rat = settle("", current, wantSafety, req);   // default: where safety goes
    for (const TrafficState &t : req.traffic)
        if (t.trafficClass == "infotainment")
            resp.classRat[t.trafficClass] = settle(t.trafficClass, t.rat, wantInfotainment, req);
    return resp;
}
```

## Plugging it in

1. Put the header in `framework/src/multirat/policies/`.
2. Register the name in `RatPolicyFactory::create()` (`policies/RatPolicyFactory.cc`):

   ```cpp
   #include "policies/MyPolicy.h"
   ...
   if (name == "MyPolicy")
       return Ptr(new MyPolicy());
   ```

3. Rebuild (`dash/build-image.sh`, or `tools/build.sh` on your own toolchain). Only the
   framework is recompiled, not the toolchain: a few minutes.
4. Run any scenario with the policy:

   ```bash
   dash/mrv run MultiRatHighway_Base --sim-time-limit=120s '--*.car[*].multiRatAppManager.policy="MyPolicy"'
   ```

   or add a config to `simulations/omnetpp.ini` that sets `*.car[*].multiRatAppManager.policy`.

5. Compare it with the others: add it to `dash/run-experiment.sh` (`--policy`) and run the test
   bench with it, `bench/run.sh --only "my_policy sinr only_dsrc only_wifi only_nr"`
   ([bench/README.md](../bench/README.md)).

**Parameters.** To make a value configurable, add a parameter to `MultiRatAppManager.ned`, a field
to `PolicyParams` (`IRatSelectionPolicy.h`), read it where the manager fills `PolicyParams`
(`MultiRatAppManager.cc`), and pass it to the constructor in the factory. `timeToTrigger`,
`sinrSwitchMargin`, `loadSwitchMargin` and `latencyBudget` already go this way.

## The built-in policies

They share a base, `TimeToTriggerPolicy`, which splits a decision in two:

- `prefer(current, rats)` is the RAT the policy would use right now: the current one unless
  another is better by the policy's own margin.
- The base switches only after the same different RAT has been preferred for `timeToTrigger`
  (1 s). If the current RAT is not usable, the preferred one is taken at once.

They use `connection.currentRat` and `rats` only, and put every traffic class on the same RAT.

| Policy | `prefer()` | Uses |
|---|---|---|
| `CoveragePriority` | First usable RAT in the order DSRC, WiFi, NR, LTE, 6G; stays unless a higher-priority one is usable. | `inRange` |
| `Sinr` | Largest `sinrDb − minSinrDb`; another RAT must be better by `sinrSwitchMargin` (3 dB). | `sinrDb`, `minSinrDb` |
| `LatencyQos` | Latency of a RAT is half its `probeRttMeanMs`. Highest `linkRateMbps` among RATs within `latencyBudget` (100 ms), else lowest latency; another RAT must offer 25 % more link rate. | `probeRttMeanMs`, `linkRateMbps` |
| `Load` | Lowest sensed `load` among DSRC and WiFi; another RAT must be lower by `loadSwitchMargin` (0.15). A RAT without a load figure (NR) is used only when neither is usable. | `load` |
| `Ensemble` | Weighted vote of the four above (`ensembleWeight*`); the leader must beat the current RAT by more than `ensembleStickiness` votes. Time-to-trigger is applied to the outcome of the vote. | all of the above |
| `Ml` | The RAT last passed to `MlPolicy::suggest()` if usable, else as CoveragePriority. Nothing calls `suggest()` yet. | |

**Baselines.** `OnlyDsrc`, `OnlyWifi` and `OnlyNr` (`SingleRatPolicy.h`) use one RAT and never
another: they ask for it whenever it is usable and otherwise answer `NONE`, so a car stays on it
even out of range. The test bench ([bench/README.md](../bench/README.md)) compares the policies
with them.

To write a policy the same way, derive from `TimeToTriggerPolicy` and implement `prefer()` and
`name()`; `SinrPolicy.h` is the shortest example.

## Not available to a policy

By the rule at the top:

- Other vehicles' state, or neighbours.
- Anything only the infrastructure knows, such as how loaded a cell is.
- Whether a request reached the server, other than through the reply that comes back.

Not built:

- The vehicle's planned route or destination.
- Per-packet events: traffic results arrive as counts per decision window.
- Policies in another language or process. A policy is a C++ class compiled into the framework.
  The request and response are plain data so that a bridge can be added without changing them.
