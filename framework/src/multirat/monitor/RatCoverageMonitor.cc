//
// RatCoverageMonitor.cc
//
#include "RatCoverageMonitor.h"

#include <algorithm>
#include <cctype>
#include <cmath>

#include "inet/mobility/contract/IMobility.h"
#include "inet/common/geometry/common/Coord.h"

namespace multiratvanet {

using namespace omnetpp;

Define_Module(RatCoverageMonitor);

static bool icontains(const std::string &hay, const std::string &needle)
{
    if (needle.empty())
        return false;
    std::string h = hay, n = needle;
    std::transform(h.begin(), h.end(), h.begin(), ::tolower);
    std::transform(n.begin(), n.end(), n.begin(), ::tolower);
    return h.find(n) != std::string::npos;
}

void RatCoverageMonitor::initialize()
{
    updateInterval_ = par("updateInterval").doubleValue();
    useDistance_ = par("useDistance").boolValue();
    useSignal_ = par("useSignal").boolValue();
    txPowerDbm_ = par("txPowerDbm").doubleValue();
    pathLossExponent_ = par("pathLossExponent").doubleValue();
    referenceLossDb_ = par("referenceLossDb").doubleValue();

    // Per-RAT configuration.
    auto setCfg = [this](RatId id, const char *has, const char *range, const char *thr,
                         const char *lat, const char *cap, const char *infra) {
        RatCfg &c = cfg_[(int)id];
        c.has = par(has).boolValue();
        c.range = par(range).doubleValue();
        c.rssiThreshold = par(thr).doubleValue();
        c.latencyMs = par(lat).doubleValue();
        c.capacityMbps = par(cap).doubleValue();
        c.infraType = par(infra).stdstringValue();
    };
    setCfg(RatId::DSRC, "hasDsrc", "dsrcRange", "dsrcRssiThreshold", "dsrcLatencyMs", "dsrcCapacityMbps", "dsrcInfraType");
    setCfg(RatId::WIFI, "hasWifi", "wifiRange", "wifiRssiThreshold", "wifiLatencyMs", "wifiCapacityMbps", "wifiInfraType");
    setCfg(RatId::LTE,  "hasLte",  "lteRange",  "lteRssiThreshold",  "lteLatencyMs",  "lteCapacityMbps",  "lteInfraType");
    setCfg(RatId::NR,   "hasNr",   "nrRange",   "nrRssiThreshold",   "nrLatencyMs",   "nrCapacityMbps",   "nrInfraType");
    setCfg(RatId::SIXG, "hasSixG", "sixgRange", "sixgRssiThreshold", "sixgLatencyMs", "sixgCapacityMbps", "sixgInfraType");

    inRangeSignal_[(int)RatId::DSRC] = registerSignal("dsrcInRange");
    inRangeSignal_[(int)RatId::WIFI] = registerSignal("wifiInRange");
    inRangeSignal_[(int)RatId::LTE]  = registerSignal("lteInRange");
    inRangeSignal_[(int)RatId::NR]   = registerSignal("nrInRange");
    inRangeSignal_[(int)RatId::SIXG] = registerSignal("sixgInRange");
    rssiSignal_[(int)RatId::DSRC] = registerSignal("dsrcRssi");
    rssiSignal_[(int)RatId::WIFI] = registerSignal("wifiRssi");
    rssiSignal_[(int)RatId::LTE]  = registerSignal("lteRssi");
    rssiSignal_[(int)RatId::NR]   = registerSignal("nrRssi");
    rssiSignal_[(int)RatId::SIXG] = registerSignal("sixgRssi");
    coverageCountSignal_ = registerSignal("coverageCount");
    connectivitySignal_ = registerSignal("connectivity");
    outageEventSignal_ = registerSignal("outageEvent");

    metrics_.resize((int)RatId::COUNT);
    for (int i = 0; i < (int)RatId::COUNT; ++i) {
        metrics_[i].id = static_cast<RatId>(i);
        metrics_[i].present = cfg_[i].has;
        metrics_[i].estLatencyMs = cfg_[i].latencyMs;
        metrics_[i].capacityMbps = cfg_[i].capacityMbps;
        minInfraDist_[i] = 1e9;
    }

    // Resolve the vehicle's own mobility submodule.
    cModule *car = getParentModule();
    cModule *mob = car ? car->getSubmodule("mobility") : nullptr;
    selfMobility_ = mob ? dynamic_cast<inet::IMobility *>(mob) : nullptr;
    if (!selfMobility_)
        EV_WARN << "RatCoverageMonitor: no 'mobility' submodule found on parent; "
                   "distance-based coverage disabled." << endl;

    discoverInfrastructure();

    lastSampleTime_ = simTime().dbl();
    timer_ = new cMessage("coverageUpdate");
    scheduleAt(simTime() + updateInterval_, timer_);
    refresh();
}

void RatCoverageMonitor::discoverInfrastructure()
{
    cModule *system = getSimulation()->getSystemModule();
    if (system)
        collectInfra(system);

    for (int i = 0; i < (int)RatId::COUNT; ++i)
        if (cfg_[i].has && !cfg_[i].infraType.empty())
            EV_INFO << "RatCoverageMonitor: RAT " << ratName((RatId)i) << " discovered "
                    << infra_[i].size() << " infrastructure node(s) matching '"
                    << cfg_[i].infraType << "'." << endl;
}

void RatCoverageMonitor::collectInfra(cModule *root)
{
    for (cModule::SubmoduleIterator it(root); !it.end(); ++it) {
        cModule *sub = *it;
        const char *typeName = sub->getComponentType() ? sub->getComponentType()->getName() : "";
        for (int i = 0; i < (int)RatId::COUNT; ++i) {
            if (!cfg_[i].has || cfg_[i].infraType.empty())
                continue;
            if (icontains(typeName, cfg_[i].infraType)) {
                cModule *mob = sub->getSubmodule("mobility");
                if (mob) {
                    if (auto *im = dynamic_cast<inet::IMobility *>(mob))
                        infra_[i].push_back(im);
                }
            }
        }
        collectInfra(sub); // recurse into the whole network tree
    }
}

double RatCoverageMonitor::proxyRssiDbm(double distanceMeters) const
{
    double d = std::max(distanceMeters, 1.0);
    return txPowerDbm_ - (referenceLossDb_ + 10.0 * pathLossExponent_ * std::log10(d));
}

void RatCoverageMonitor::refresh()
{
    inet::Coord myPos;
    bool haveMyPos = false;
    if (selfMobility_) {
        myPos = selfMobility_->getCurrentPosition();
        haveMyPos = true;
        if (myPos.x < selfXmin_) selfXmin_ = myPos.x;
        if (myPos.x > selfXmax_) selfXmax_ = myPos.x;
        if (myPos.y < selfYmin_) selfYmin_ = myPos.y;
        if (myPos.y > selfYmax_) selfYmax_ = myPos.y;
    }

    long coverage = 0;
    for (int i = 0; i < (int)RatId::COUNT; ++i) {
        RatMetrics &m = metrics_[i];
        m.lastUpdate = simTime().dbl();
        if (!cfg_[i].has) {
            m.inRange = false;
            continue;
        }

        double minDist = 1e9;
        if (cfg_[i].infraType.empty()) {
            // Idealized umbrella: always covered when equipped.
            minDist = 0.0;
        }
        else if (haveMyPos) {
            for (inet::IMobility *im : infra_[i]) {
                double d = myPos.distance(im->getCurrentPosition());
                if (d < minDist)
                    minDist = d;
            }
        }

        double rssi = proxyRssiDbm(minDist);
        bool distOk = !useDistance_ || (minDist <= cfg_[i].range);
        bool sigOk = !useSignal_ || (rssi >= cfg_[i].rssiThreshold);
        bool inRange = distOk && sigOk && (cfg_[i].infraType.empty() || !infra_[i].empty());

        m.inRange = inRange;
        m.rssiDbm = rssi;
        m.sinrDb = rssi + 100.0; // crude SINR proxy from RSSI (dB above -100 noise floor)
        m.distanceToInfra = minDist;
        if (minDist < minInfraDist_[i])
            minInfraDist_[i] = minDist;

        emit(inRangeSignal_[i], (long)(inRange ? 1 : 0));
        emit(rssiSignal_[i], rssi);
        if (inRange)
            ++coverage;
    }
    emit(coverageCountSignal_, coverage);

    // --- CAV connectivity / availability accounting ---
    // Attribute the interval since the previous sample to the coverage state
    // that held during it (time-weighted), then handle outage transitions.
    double now = simTime().dbl();
    double dt = now - lastSampleTime_;
    if (dt > 0) {
        totalTime_ += dt;
        coverageIntegral_ += (double)prevCoverage_ * dt;
        if (prevCoverage_ >= 1)
            connectedTime_ += dt;
        else
            outageTime_ += dt;
        if (prevCoverage_ >= 2)
            multiConnTime_ += dt;
    }
    lastSampleTime_ = now;

    bool nowOutage = (coverage == 0);
    if (nowOutage && !wasOutage_) {          // entering an outage span
        ++outageEpisodes_;
        curOutageStart_ = now;
        emit(outageEventSignal_, (long)1);
    }
    else if (!nowOutage && wasOutage_) {     // leaving an outage span
        double dur = now - curOutageStart_;
        if (dur > maxOutageDuration_)
            maxOutageDuration_ = dur;
    }
    wasOutage_ = nowOutage;
    prevCoverage_ = coverage;
    emit(connectivitySignal_, (long)(nowOutage ? 0 : 1));
}

bool RatCoverageMonitor::isInRange(RatId r) const
{
    int i = ratIndex(r);
    if (i < 0 || i >= (int)metrics_.size())
        return false;
    return metrics_[i].inRange;
}

void RatCoverageMonitor::handleMessage(cMessage *msg)
{
    if (msg == timer_) {
        refresh();
        scheduleAt(simTime() + updateInterval_, timer_);
    }
    else {
        delete msg;
    }
}

void RatCoverageMonitor::finish()
{
    // Close a still-open outage span and fold the final interval into the totals.
    double now = simTime().dbl();
    double dt = now - lastSampleTime_;
    if (dt > 0) {
        totalTime_ += dt;
        coverageIntegral_ += (double)prevCoverage_ * dt;
        if (prevCoverage_ >= 1)
            connectedTime_ += dt;
        else
            outageTime_ += dt;
        if (prevCoverage_ >= 2)
            multiConnTime_ += dt;
    }
    if (wasOutage_) {
        double dur = now - curOutageStart_;
        if (dur > maxOutageDuration_)
            maxOutageDuration_ = dur;
    }

    double T = totalTime_ > 0 ? totalTime_ : 1.0;
    recordScalar("connectivityRatio", connectedTime_ / T);       // fraction of life with >=1 RAT
    recordScalar("outageRatio", outageTime_ / T);                // fraction of life with 0 RATs
    recordScalar("outageTimeTotal", outageTime_, "s");
    recordScalar("outageCount", outageEpisodes_);
    recordScalar("maxOutageDuration", maxOutageDuration_, "s");
    recordScalar("multiConnectivityRatio", multiConnTime_ / T);  // fraction with >=2 RATs (redundancy)
    recordScalar("avgAvailableRats", coverageIntegral_ / T);     // mean simultaneous RATs in range

    // Diagnostics: how many infra nodes each RAT discovered and the vehicle's
    // closest approach to them (helps validate RSU/AP placement vs. the track).
    for (int i = 0; i < (int)RatId::COUNT; ++i) {
        if (!cfg_[i].has)
            continue;
        std::string base = ratName((RatId)i);
        recordScalar((base + ".infraNodes").c_str(), (double)infra_[i].size());
        recordScalar((base + ".minInfraDist").c_str(),
                minInfraDist_[i] >= 1e9 ? -1.0 : minInfraDist_[i], "m");
    }
    // Observed vehicle coordinate range (to align RSU/AP placement to the frame).
    if (selfXmax_ >= selfXmin_) {
        recordScalar("selfXmin", selfXmin_, "m");
        recordScalar("selfXmax", selfXmax_, "m");
        recordScalar("selfYmin", selfYmin_, "m");
        recordScalar("selfYmax", selfYmax_, "m");
    }

    cancelAndDelete(timer_);
    timer_ = nullptr;
}

} // namespace multiratvanet
