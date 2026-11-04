//
// RatCoverageMonitor.h
//
#ifndef MULTIRATVANET_RATCOVERAGEMONITOR_H
#define MULTIRATVANET_RATCOVERAGEMONITOR_H

#include <omnetpp.h>
#include <cmath>
#include <string>
#include <map>
#include <vector>
#include "base/RatTypes.h"

namespace inet { class IMobility; }

namespace multiratvanet {

//
// Estimates per-RAT coverage for the parent vehicle and publishes a metric
// vector consumed by the MultiRatAppManager.
//
// signalSource "measured": every metric comes from the running simulation.
//   signal   estimated uplink SINR, since cars send uplink: 802.11 = SNIR of beacons from the
//            AP/RSU the car is associated with, cellular = Simu5G downlink SINR; both minus
//            the transmit-power difference between infrastructure and car
//   load     802.11: channel busy ratio seen by the car's radio; cellular: uplink
//            resource-block utilisation of the car's serving cell
//   capacity link rate x free share (802.11: rate the MAC actually uses;
//            cellular: spectral efficiency from SINR x cell bandwidth)
//   latency  path latency + packet service time / (1 - load)
//   in range measured recently, filtered SINR above the RAT's minimum (with
//            hysteresis), and for 802.11 associated with an AP/RSU
// signalSource "proxy": the original distance-based estimate and fixed numbers.
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
    virtual void receiveSignal(omnetpp::cComponent *source, omnetpp::simsignal_t id, omnetpp::intval_t value, omnetpp::cObject *details) override;

  public:
    virtual ~RatCoverageMonitor();

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
    void accountBusy(int rat, double now);
    const omnetpp::cModule *servingCellMac(int rat, double *bandwidthMHz) const;

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
        double sinrDb = NAN;        // filtered
        double load = 0;            // filtered, 0..1
        double time = -1;           // sim time of the last window with samples
        long samples = 0;           // total samples over the run (diagnostics)
        bool inRange = false;       // previous decision, for the entry/exit hysteresis
        bool associated = false;    // 802.11: STA associated with an AP/RSU
    };
    // 802.11 channel busy accounting (CBR), per RAT
    struct Busy {
        bool rx = false, tx = false;
        double since = 0;           // time of the last state change
        double accum = 0;           // busy time since the last refresh
        double windowStart = 0;
    };
    Busy busy_[(int)RatId::COUNT];
    // averages of what the policies were given while each RAT was in range (diagnostics)
    struct InputStats { long n = 0; double sinrMargin = 0, load = 0, capacity = 0, latency = 0; };
    InputStats inputStats_[(int)RatId::COUNT];
    // cellular: uplink resource blocks allocated per TTI, per gNB MAC, since the last refresh
    std::map<const omnetpp::cModule *, std::pair<double, long>> servedBlocks_;
    double linkRateMbps_[(int)RatId::COUNT];   // 802.11: rate data frames are sent at
    double pathLatencyMs_[(int)RatId::COUNT];
    double minSinrDb_[(int)RatId::COUNT];
    double uplinkOffsetDb_[(int)RatId::COUNT];  // cellular: cell power - car power (dB)
    double inRangeHysteresisDb_ = 2;
    double filterWeight_ = 0.5;
    double refPacketBits_ = 10000;
    omnetpp::cModule *binder_ = nullptr;
    Window window_[(int)RatId::COUNT];
    Measured measured_[(int)RatId::COUNT];
    bool measuredMode_ = true;
    double measurementMaxAge_ = 0.5;
    std::string dsrcNic_, wifiNic_;
    omnetpp::simsignal_t measuredSinrDlSignal_ = -1;
    omnetpp::simsignal_t servedBlocksUlSignal_ = -1;

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
