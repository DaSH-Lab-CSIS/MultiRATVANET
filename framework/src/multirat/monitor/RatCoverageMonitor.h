//
// RatCoverageMonitor.h
//
#ifndef MULTIRATVANET_RATCOVERAGEMONITOR_H
#define MULTIRATVANET_RATCOVERAGEMONITOR_H

#include <omnetpp.h>
#include <cmath>
#include <string>
#include <vector>
#include "base/RatTypes.h"

namespace inet { class IMobility; }

namespace multiratvanet {

//
// Estimates per-RAT coverage for the parent vehicle and publishes a metric
// vector consumed by the MultiRatAppManager.
//
// signalSource "measured": signal and coverage come from the radios themselves
// (802.11 beacons from RSUs/APs, Simu5G downlink SINR of the serving cell).
// signalSource "proxy": the original distance-based estimate.
//
class  RatCoverageMonitor : public omnetpp::cSimpleModule, public omnetpp::cListener
{
  public:
    // Snapshot of the latest per-RAT metrics (indexed by ratIndex()).
    const RatMetricsVec &getMetrics() const { return metrics_; }
    bool isInRange(RatId r) const;

  protected:
    virtual void initialize() override;
    virtual void handleMessage(omnetpp::cMessage *msg) override;
    virtual void finish() override;

    // measurement feeds (signalSource == "measured")
    virtual void receiveSignal(omnetpp::cComponent *source, omnetpp::simsignal_t id, omnetpp::cObject *obj, omnetpp::cObject *details) override;
    virtual void receiveSignal(omnetpp::cComponent *source, omnetpp::simsignal_t id, double value, omnetpp::cObject *details) override;

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
    void applyMeasurement(int rat, RatMetrics &m, double now);
    int ratOfWlan(const omnetpp::cModule *nic) const;

    // One window of samples per RAT, collected between two refresh() calls.
    // 802.11: strongest infrastructure beacon in the window; cellular: mean SINR.
    struct Window {
        int n = 0;
        double bestRssiDbm = -1e9;  // 802.11 only
        double snirOfBest = -1e9;   // 802.11: SNIR of that beacon (dB)
        double sinrSum = 0;         // cellular: sum of SINR samples (dB)
    };
    struct Measured {
        bool valid = false;
        double rssiDbm = NAN;       // NaN for cellular (Simu5G reports SINR, not power)
        double sinrDb = NAN;
        double time = -1;           // sim time of the last window with samples
        long samples = 0;           // total samples over the run (diagnostics)
    };
    Window window_[(int)RatId::COUNT];
    Measured measured_[(int)RatId::COUNT];
    bool measuredMode_ = true;
    double measurementMaxAge_ = 0.5;
    double cellularMinSinrDb_[(int)RatId::COUNT];
    std::string dsrcNic_, wifiNic_;
    omnetpp::simsignal_t measuredSinrDlSignal_ = -1;

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
