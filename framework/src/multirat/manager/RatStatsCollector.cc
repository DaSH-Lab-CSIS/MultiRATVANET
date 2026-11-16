//
// RatStatsCollector.cc
//
#include "RatStatsCollector.h"

#include "MultiRatAppManager.h"
#include "RatCoverageMonitor.h"

#include <cmath>
#include "inet/mobility/contract/IMobility.h"

namespace multiratvanet {

using namespace omnetpp;

Define_Module(RatStatsCollector);

void RatStatsCollector::initialize()
{
    statInterval_ = par("statInterval").doubleValue();

    vehiclesSignal_[(int)RatId::DSRC] = registerSignal("vehiclesDsrc");
    vehiclesSignal_[(int)RatId::WIFI] = registerSignal("vehiclesWifi");
    vehiclesSignal_[(int)RatId::LTE]  = registerSignal("vehiclesLte");
    vehiclesSignal_[(int)RatId::NR]   = registerSignal("vehiclesNr");
    vehiclesSignal_[(int)RatId::SIXG] = registerSignal("vehiclesSixg");
    vehiclesUnconnectedSignal_ = registerSignal("vehiclesUnconnected");
    vehiclesTotalSignal_       = registerSignal("vehiclesTotal");

    avgRssiSignal_[(int)RatId::DSRC] = registerSignal("avgRssiDsrc");
    avgRssiSignal_[(int)RatId::WIFI] = registerSignal("avgRssiWifi");
    avgRssiSignal_[(int)RatId::LTE]  = registerSignal("avgRssiLte");
    avgRssiSignal_[(int)RatId::NR]   = registerSignal("avgRssiNr");
    avgRssiSignal_[(int)RatId::SIXG] = registerSignal("avgRssiSixg");

    double startTime = par("startTime").doubleValue();
    timer_ = new cMessage("ratStatsSample");
    scheduleAt(simTime() + startTime, timer_);
}

void RatStatsCollector::collectCars(cModule *root,
        long vehiclesPerRat[], long &connected, long &unconnected,
        double rssiSum[], long rssiCount[])
{
    for (cModule::SubmoduleIterator it(root); !it.end(); ++it) {
        cModule *sub = *it;
        // A vehicle is any node that carries the RAT control plane. Reading the
        // manager/monitor via their submodule names keeps this decoupled from
        // the concrete car NED type (dynamically created by SUMO/Veins).
        cModule *mgrMod = sub->getSubmodule("multiRatAppManager");
        if (mgrMod) {
            if (auto *mgr = dynamic_cast<MultiRatAppManager *>(mgrMod)) {
                RatId active = mgr->getActiveRat();
                if (active == RatId::NONE)
                    ++unconnected;
                else {
                    ++vehiclesPerRat[ratIndex(active)];
                    ++connected;
                }
            }
            // Network-wide RSSI: average over vehicles where each RAT is in range.
            if (auto *monMod = sub->getSubmodule("ratCoverageMonitor")) {
                if (auto *mon = dynamic_cast<RatCoverageMonitor *>(monMod)) {
                    const RatMetricsVec &metrics = mon->getMetrics();
                    for (int i = 0; i < (int)RatId::COUNT && i < (int)metrics.size(); ++i) {
                        // cellular reports SINR only (rssiDbm is NaN in measured mode)
                        if (metrics[i].present && metrics[i].inRange && !std::isnan(metrics[i].rssiDbm)) {
                            rssiSum[i] += metrics[i].rssiDbm;
                            ++rssiCount[i];
                        }
                    }
                }
            }
        }
        collectCars(sub, vehiclesPerRat, connected, unconnected, rssiSum, rssiCount);
    }
}

void RatStatsCollector::sample()
{
    long vehiclesPerRat[(int)RatId::COUNT] = {0};
    double rssiSum[(int)RatId::COUNT] = {0};
    long rssiCount[(int)RatId::COUNT] = {0};
    long connected = 0, unconnected = 0;

    collectCars(getSimulation()->getSystemModule(),
                vehiclesPerRat, connected, unconnected, rssiSum, rssiCount);

    for (int i = 0; i < (int)RatId::COUNT; ++i)
        emit(vehiclesSignal_[i], vehiclesPerRat[i]);
    emit(vehiclesUnconnectedSignal_, unconnected);
    emit(vehiclesTotalSignal_, connected + unconnected);

    // Only emit an average when at least one vehicle is in range for that RAT,
    // so idle RATs do not skew the record with a meaningless placeholder value.
    for (int i = 0; i < (int)RatId::COUNT; ++i)
        if (rssiCount[i] > 0)
            emit(avgRssiSignal_[i], rssiSum[i] / rssiCount[i]);
}

void RatStatsCollector::handleMessage(cMessage *msg)
{
    if (msg == timer_) {
        sample();
        scheduleAt(simTime() + statInterval_, timer_);
    }
    else {
        delete msg;
    }
}

void RatStatsCollector::finish()
{
    // Where the infrastructure stood (once per run; positions in NED display strings are not
    // in the results otherwise): "infra.<module>.x/.y" for every top-level node that has a
    // mobility module and is not a vehicle.
    for (cModule::SubmoduleIterator it(getSimulation()->getSystemModule()); !it.end(); ++it) {
        cModule *node = *it;
        if (node->getSubmodule("multiRatAppManager"))
            continue;
        auto *mob = dynamic_cast<inet::IMobility *>(node->getSubmodule("mobility"));
        if (!mob)
            continue;
        inet::Coord p = mob->getCurrentPosition();
        std::string base = std::string("infra.") + node->getFullName();
        recordScalar((base + ".x").c_str(), p.x, "m");
        recordScalar((base + ".y").c_str(), p.y, "m");
    }
    cancelAndDelete(timer_);
    timer_ = nullptr;
}

} // namespace multiratvanet
