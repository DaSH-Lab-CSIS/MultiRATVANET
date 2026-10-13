//
// RatStatsCollector.h - network-wide periodic RAT statistics.
//
// A single, network-scoped module that samples every `statInterval` (0.1s by
// default) and records, across all live vehicles:
//   * how many vehicles are currently connected on each active RAT, and
//   * the network-wide average RSSI proxy per RAT (over in-range vehicles).
//
// Vehicles are created/destroyed dynamically by SUMO/Veins, so the collector
// re-discovers them on every sample by scanning the module tree for nodes that
// carry a `multiRatAppManager` submodule.
//
#ifndef MULTIRATVANET_RATSTATSCOLLECTOR_H
#define MULTIRATVANET_RATSTATSCOLLECTOR_H

#include <omnetpp.h>
#include "base/RatTypes.h"

namespace multiratvanet {

class MultiRatAppManager;
class RatCoverageMonitor;

//
// Aggregates per-RAT connectivity and signal-strength statistics over all
// vehicles at a fixed sampling interval.
//
class RatStatsCollector : public omnetpp::cSimpleModule
{
  protected:
    virtual void initialize() override;
    virtual void handleMessage(omnetpp::cMessage *msg) override;
    virtual void finish() override;

  private:
    void sample();
    void collectCars(omnetpp::cModule *root,
                     long vehiclesPerRat[], long &connected, long &unconnected,
                     double rssiSum[], long rssiCount[]);

    double statInterval_ = 0.1;
    omnetpp::cMessage *timer_ = nullptr;

    // Per-RAT connected-vehicle count signals (indexed by ratIndex()).
    omnetpp::simsignal_t vehiclesSignal_[(int)RatId::COUNT];
    omnetpp::simsignal_t vehiclesUnconnectedSignal_ = -1;
    omnetpp::simsignal_t vehiclesTotalSignal_ = -1;

    // Per-RAT network-wide average RSSI signals (indexed by ratIndex()).
    omnetpp::simsignal_t avgRssiSignal_[(int)RatId::COUNT];
};

} // namespace multiratvanet

#endif
