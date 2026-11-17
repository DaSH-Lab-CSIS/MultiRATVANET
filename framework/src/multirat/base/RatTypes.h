//
// RatTypes.h - shared type definitions for the multi-RAT handover framework.
//
// These types are intentionally free of OMNeT++/INET dependencies so that the
// RAT-selection policies can be unit-reasoned about in isolation.
//
#ifndef MULTIRATVANET_RATTYPES_H
#define MULTIRATVANET_RATTYPES_H

#include <cmath>
#include <string>
#include <vector>

namespace multiratvanet {

// Radio access technologies handled by the framework. The numeric values are
// used as stable indices into per-RAT metric/interface vectors, so do not
// reorder without updating the corresponding wiring.
enum class RatId {
    DSRC = 0,   // IEEE 802.11p @ 5.9 GHz (wlan[0])
    WIFI = 1,   // IEEE 802.11 a/g/n infrastructure (wlan[1])
    LTE  = 2,   // 4G LTE via Simu5G cellularNic (macro eNB)
    NR   = 3,   // 5G NR via Simu5G cellularNic (gNB)
    SIXG = 4,   // 6G placeholder interface
    COUNT = 5,
    NONE = -1
};

inline const char *ratName(RatId r) {
    switch (r) {
        case RatId::DSRC: return "DSRC";
        case RatId::WIFI: return "WIFI";
        case RatId::LTE:  return "LTE";
        case RatId::NR:   return "NR";
        case RatId::SIXG: return "6G";
        case RatId::NONE: return "NONE";
        default:          return "?";
    }
}

inline int ratIndex(RatId r) { return static_cast<int>(r); }

// What a vehicle knows about one of its RATs, refreshed by the RatCoverageMonitor. Everything here
// is something the car's own radio observes; nothing comes from the infrastructure's side or from
// other vehicles. docs/POLICY_REFERENCE.md describes each field.
struct RatMetrics {
    RatId id = RatId::NONE;
    bool present = false;      // this RAT exists on the node (interface up)
    bool inRange = false;      // usable now (computed by the harness): the only RATs a policy may choose
    bool linked = false;       // 802.11: associated with an RSU/AP; cellular: attached to a serving cell
    double sinrDb = -50.0;     // signal-to-interference-plus-noise ratio (dB), uplink estimate, filtered
    double minSinrDb = -1e9;   // lowest usable SINR for this RAT (dB); sinrDb - minSinrDb = margin
    double rssiDbm = -200.0;   // received signal strength (dBm); NaN where the radio does not report it
    double load = 0.0;         // channel busy ratio the radio senses [0..1]; NaN for cellular (a UE cannot see cell load)
    double linkRateMbps = 0.0; // rate the radio would send at with the channel to itself (Mbps)
    double probeRttMs = NAN;      // round-trip time of the latest probe echoed over this RAT (ms); NaN = none yet
    double probeRttMeanMs = NAN;  // mean round trip of the probes of the last second (ms); NaN = none echoed
    double probeLoss = NAN;       // share of recent probes that were not echoed [0..1]; NaN = none sent
    double probeAge = -1.0;       // s since the latest echo; -1 = never
    double measurementAge = -1.0; // s since the signal was last measured; -1 = never (or not measured: proxy mode)
    double lastUpdate = 0.0;   // sim time (s) of last refresh
};

using RatMetricsVec = std::vector<RatMetrics>;

} // namespace multiratvanet

#endif
