//
// RatCoverageMonitor.h
//
#ifndef MULTIRATVANET_RATCOVERAGEMONITOR_H
#define MULTIRATVANET_RATCOVERAGEMONITOR_H

#include <omnetpp.h>
#include <vector>
#include "base/RatTypes.h"

namespace inet { class IMobility; }

namespace multiratvanet {

//
// Estimates per-RAT coverage for the parent vehicle and publishes a metric
// vector consumed by the MultiRatAppManager.
//
class  RatCoverageMonitor : public omnetpp::cSimpleModule
{
  public:
    // Snapshot of the latest per-RAT metrics (indexed by ratIndex()).
    const RatMetricsVec &getMetrics() const { return metrics_; }
    bool isInRange(RatId r) const;

  protected:
    virtual void initialize() override;
    virtual void handleMessage(omnetpp::cMessage *msg) override;
    virtual void finish() override;

  private:
    struct RatCfg {
        bool has = false;
        double range = 0;          // m
        double rssiThreshold = 0;  // dBm
        double latencyMs = 0;
        double capacityMbps = 0;
        std::string infraType;     // NED type marker for infrastructure
    };

    void discoverInfrastructure();
    void collectInfra(omnetpp::cModule *root);
    void refresh();
    double proxyRssiDbm(double distanceMeters) const;

    RatCfg cfg_[(int)RatId::COUNT];
    std::vector<inet::IMobility *> infra_[(int)RatId::COUNT];
    inet::IMobility *selfMobility_ = nullptr;

    double minInfraDist_[(int)RatId::COUNT]; // closest approach to each RAT's infra (m)
    double selfXmin_ = 1e9, selfXmax_ = -1e9;
    double selfYmin_ = 1e9, selfYmax_ = -1e9;

    RatMetricsVec metrics_;

    omnetpp::cMessage *timer_ = nullptr;
    double updateInterval_ = 0.1;
    bool useDistance_ = true;
    bool useSignal_ = true;
    double txPowerDbm_ = 23.0;
    double pathLossExponent_ = 2.5;
    double referenceLossDb_ = 40.0;

    omnetpp::simsignal_t inRangeSignal_[(int)RatId::COUNT];
    omnetpp::simsignal_t rssiSignal_[(int)RatId::COUNT];
    omnetpp::simsignal_t coverageCountSignal_ = -1;
    omnetpp::simsignal_t connectivitySignal_ = -1; // 1 while >=1 RAT usable, else 0
    omnetpp::simsignal_t outageEventSignal_ = -1;  // 1 per new outage episode

    // --- CAV connectivity / availability accounting (time-weighted) ---
    double lastSampleTime_ = 0.0;      // sim time of the previous refresh()
    double totalTime_ = 0.0;           // observed lifetime of this node (s)
    double connectedTime_ = 0.0;       // time with >=1 RAT usable (s)
    double outageTime_ = 0.0;          // time with 0 RATs usable (s)
    double multiConnTime_ = 0.0;       // time with >=2 RATs usable (s)
    double coverageIntegral_ = 0.0;    // integral of coverageCount over time
    long   outageEpisodes_ = 0;        // number of distinct outage spans
    double curOutageStart_ = 0.0;      // start time of the ongoing outage span
    double maxOutageDuration_ = 0.0;   // longest single outage span (s)
    bool   wasOutage_ = false;         // previous-sample outage state
    long   prevCoverage_ = 0;          // coverageCount held over the last interval
};

} // namespace multiratvanet

#endif
