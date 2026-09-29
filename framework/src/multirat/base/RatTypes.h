//
// RatTypes.h - shared type definitions for the multi-RAT handover framework.
//
// These types are intentionally free of OMNeT++/INET dependencies so that the
// RAT-selection policies can be unit-reasoned about in isolation.
//
#ifndef MULTIRATVANET_RATTYPES_H
#define MULTIRATVANET_RATTYPES_H

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

// Per-RAT observable state, refreshed by the RatCoverageMonitor.
struct RatMetrics {
    RatId id = RatId::NONE;
    bool present = false;      // this RAT exists on the node (interface up)
    bool inRange = false;      // hard precondition: within usable coverage
    double rssiDbm = -200.0;   // received signal strength (dBm)
    double sinrDb = -50.0;     // signal-to-interference-plus-noise ratio (dB)
    double distanceToInfra = 1e9; // metres to nearest AP/RSU/gNB (if known)
    double estLatencyMs = 1e6; // estimated one-way/round latency proxy (ms)
    double load = 0.0;         // normalized channel/cell load [0..1]
    double capacityMbps = 0.0; // nominal/estimated available rate (Mbps)
    double lastUpdate = 0.0;   // sim time (s) of last refresh
};

using RatMetricsVec = std::vector<RatMetrics>;

} // namespace multiratvanet

#endif
