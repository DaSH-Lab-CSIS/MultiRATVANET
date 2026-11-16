//
// MultiRatAppManager.cc
//
#include "MultiRatAppManager.h"

#include "RatCoverageMonitor.h"
#include "policies/RatPolicyFactory.h"
#include "policies/EnsemblePolicy.h"

#include "inet/common/InitStages.h"
#include "inet/common/ModuleAccess.h"
#include "inet/networklayer/contract/IInterfaceTable.h"
#include "inet/networklayer/common/NetworkInterface.h"
#include "inet/networklayer/ipv4/IIpv4RoutingTable.h"
#include "inet/networklayer/ipv4/Ipv4Route.h"
#include "inet/networklayer/ipv4/Ipv4InterfaceData.h"
#include "inet/networklayer/contract/ipv4/Ipv4Address.h"

namespace multiratvanet {

using namespace omnetpp;
using namespace inet;

Define_Module(MultiRatAppManager);

int MultiRatAppManager::numInitStages() const
{
    return inet::NUM_INIT_STAGES;
}

void MultiRatAppManager::initialize(int stage)
{
    if (stage == inet::INITSTAGE_LOCAL) {
        decisionInterval_ = par("decisionInterval").doubleValue();
        handoverExecDelay_ = par("handoverExecDelay").doubleValue();
        handoverDelayPerRat_[(int)RatId::DSRC] = par("dsrcHandoverDelay").doubleValue();
        handoverDelayPerRat_[(int)RatId::WIFI] = par("wifiHandoverDelay").doubleValue();
        handoverDelayPerRat_[(int)RatId::LTE]  = par("lteHandoverDelay").doubleValue();
        handoverDelayPerRat_[(int)RatId::NR]   = par("nrHandoverDelay").doubleValue();
        handoverDelayPerRat_[(int)RatId::SIXG] = par("sixgHandoverDelay").doubleValue();
        pingPongWindow_ = par("pingPongWindow").doubleValue();
        decideOnlyOnCoverageChange_ = par("decideOnlyOnCoverageChange").boolValue();

        ifaceName_[(int)RatId::DSRC] = par("dsrcInterface").stdstringValue();
        ifaceName_[(int)RatId::WIFI] = par("wifiInterface").stdstringValue();
        ifaceName_[(int)RatId::LTE]  = par("lteInterface").stdstringValue();
        ifaceName_[(int)RatId::NR]   = par("nrInterface").stdstringValue();
        ifaceName_[(int)RatId::SIXG] = par("sixgInterface").stdstringValue();
        gateway_[(int)RatId::DSRC] = par("dsrcGateway").stdstringValue();
        gateway_[(int)RatId::WIFI] = par("wifiGateway").stdstringValue();
        gateway_[(int)RatId::LTE]  = par("lteGateway").stdstringValue();
        gateway_[(int)RatId::NR]   = par("nrGateway").stdstringValue();
        gateway_[(int)RatId::SIXG] = par("sixgGateway").stdstringValue();

        policy_ = RatPolicyFactory::create(par("policy").stdstringValue());
        if (auto *ens = dynamic_cast<EnsemblePolicy *>(policy_.get())) {
            ens->setWeights(par("ensembleWeightCoverage").doubleValue(),
                            par("ensembleWeightSinr").doubleValue(),
                            par("ensembleWeightLatency").doubleValue(),
                            par("ensembleWeightLoad").doubleValue());
            ens->setStickiness(par("ensembleStickiness").doubleValue());
        }
        EV_INFO << "MultiRatAppManager using policy: " << policy_->name() << endl;

        monitor_ = check_and_cast<RatCoverageMonitor *>(
                getModuleByPath(par("coverageMonitorModule").stringValue()));
        ift_ = getModuleFromPar<IInterfaceTable>(par("interfaceTableModule"), this);
        rt_ = getModuleFromPar<IIpv4RoutingTable>(par("routingTableModule"), this);

        handoverCountSignal_ = registerSignal("handoverCount");
        handoverLatencySignal_ = registerSignal("handoverLatency");
        handoverPairSignal_ = registerSignal("handoverPair");
        pingPongSignal_ = registerSignal("pingPong");
        activeRatSignal_ = registerSignal("activeRat");
        outageTimeSignal_ = registerSignal("outageTime");
        decisionCountSignal_ = registerSignal("decisionCount");
        handoverFailedSignal_ = registerSignal("handoverFailed");

        decisionTimer_ = new cMessage("ratDecision");
        applyTimer_ = new cMessage("applyHandover");
        scheduleAt(simTime() + par("startTime").doubleValue(), decisionTimer_);
    }
    else if (stage == inet::INITSTAGE_LAST) {
        // The DSRC/WiFi NICs we add on top of the Simu5G car are not seen by
        // any network-wide configurator (cars are created dynamically by SUMO),
        // and HostAutoConfigurator matches interface names exactly, so wlan0/
        // wlan1 never receive an IPv4 address. Assign them here, after every NIC
        // has registered its NetworkInterface, so the IPv4 stack has valid data.
        configureWlanInterfaces();
    }
}

void MultiRatAppManager::configureWlanInterfaces()
{
    if (!ift_)
        return;
    cModule *host = getContainingNode(this);
    uint32_t hostId = (uint32_t)host->getId();
    // One /8 block per WiFi/DSRC RAT; host id keeps addresses unique per car.
    const struct { RatId id; uint8_t block; } wlans[] = {
        { RatId::DSRC, 10 }, { RatId::WIFI, 20 }
    };
    for (const auto &w : wlans) {
        int idx = ratIndex(w.id);
        NetworkInterface *ie = ift_->findInterfaceByName(ifaceName_[idx].c_str());
        if (!ie)
            continue;
        auto *ipv4Data = ie->findProtocolDataForUpdate<Ipv4InterfaceData>();
        if (!ipv4Data)
            ipv4Data = ie->addProtocolData<Ipv4InterfaceData>();
        if (ipv4Data->getIPAddress().isUnspecified()) {
            Ipv4Address addr(w.block, (hostId >> 8) & 0xFF, hostId & 0xFF, 1);
            ipv4Data->setIPAddress(addr);
            ipv4Data->setNetmask(Ipv4Address(255, 0, 0, 0));
            ie->setBroadcast(true);
            EV_INFO << "Assigned " << addr.str() << " to " << ifaceName_[idx]
                    << " (" << ratName(w.id) << ")" << endl;
        }
    }
}

void MultiRatAppManager::accountResidency()
{
    if (current_ != RatId::NONE)
        residency_[ratIndex(current_)] += simTime().dbl() - currentSince_;
    currentSince_ = simTime().dbl();
}

void MultiRatAppManager::decide()
{
    const RatMetricsVec &metrics = monitor_->getMetrics();

    if (decideOnlyOnCoverageChange_) {
        unsigned long mask = 0;
        for (const auto &m : metrics)
            if (m.present && m.inRange)
                mask |= (1u << ratIndex(m.id));
        if (mask == lastCoverageMask_ && current_ != RatId::NONE)
            return; // no coverage change -> nothing to decide
        lastCoverageMask_ = mask;
    }

    emit(decisionCountSignal_, (long)1);
    RatId target = policy_->select(current_, metrics);

    if (target == RatId::NONE)
        return; // no usable RAT; keep whatever we had

    if (current_ == RatId::NONE) {
        attach(target);
    }
    else if (target != current_ && !inHandover_) {
        initiateHandover(target);
    }
}

void MultiRatAppManager::attach(RatId target)
{
    if (!applyDefaultRoute(target)) {
        emit(handoverFailedSignal_, (long)1);
        return;
    }
    accountResidency();
    lastRat_ = current_;
    current_ = target;
    lastSwitchTime_ = simTime().dbl();
    emit(activeRatSignal_, (long)ratIndex(current_));
    EV_INFO << "Initial RAT attach -> " << ratName(current_) << endl;
}

void MultiRatAppManager::initiateHandover(RatId target)
{
    pendingTarget_ = target;
    inHandover_ = true;
    handoverStartTime_ = simTime().dbl(); // timestamp for the measured delay
    double execDelay = handoverDelayPerRat_[ratIndex(target)];
    long fromIdx = (current_ == RatId::NONE) ? 9 : ratIndex(current_);
    emit(handoverPairSignal_, fromIdx * 10 + ratIndex(target));
    EV_INFO << "Handover initiated " << ratName(current_) << " -> " << ratName(target)
            << " (exec delay " << execDelay << "s)" << endl;
    scheduleAt(simTime() + execDelay, applyTimer_);
}

void MultiRatAppManager::applyHandover()
{
    // The target may have left coverage during the switch interruption.
    const RatMetricsVec &metrics = monitor_->getMetrics();
    int ti = ratIndex(pendingTarget_);
    bool stillUsable = ti >= 0 && ti < (int)metrics.size()
            && metrics[ti].present && metrics[ti].inRange;
    if (!stillUsable || !applyDefaultRoute(pendingTarget_)) {
        emit(handoverFailedSignal_, (long)1);
        inHandover_ = false;
        EV_WARN << "Handover to " << ratName(pendingTarget_) << " failed/aborted." << endl;
        return;
    }

    accountResidency();

    // Ping-pong: returning to the immediately previous RAT within the window.
    if (pendingTarget_ == lastRat_ && (simTime().dbl() - lastSwitchTime_) < pingPongWindow_) {
        emit(pingPongSignal_, (long)1);
        ++pingPongTotal_;
    }

    lastRat_ = current_;
    current_ = pendingTarget_;
    lastSwitchTime_ = simTime().dbl();
    inHandover_ = false;
    ++handoverTotal_;

    // Measured handover delay: elapsed sim time from the moment the switch was
    // initiated until the new default route is actually installed (i.e. the
    // make-before-break interruption the data flow really experiences).
    double handoverDelay = simTime().dbl() - handoverStartTime_;
    handoverDelaySum_ += handoverDelay;
    if (handoverDelay > handoverDelayMax_)
        handoverDelayMax_ = handoverDelay;

    emit(handoverCountSignal_, (long)1);
    emit(handoverLatencySignal_, handoverDelay);
    emit(outageTimeSignal_, handoverDelay);
    emit(activeRatSignal_, (long)ratIndex(current_));
    EV_INFO << "Handover complete -> " << ratName(current_)
            << " (measured delay " << handoverDelay << "s)" << endl;
}

bool MultiRatAppManager::applyDefaultRoute(RatId target)
{
    if (!rt_ || !ift_)
        return false;
    int idx = ratIndex(target);
    NetworkInterface *ie = ift_->findInterfaceByName(ifaceName_[idx].c_str());
    if (!ie) {
        EV_WARN << "No interface '" << ifaceName_[idx] << "' for RAT " << ratName(target) << endl;
        return false;
    }
    // The interface must carry IPv4 data (address/netmask) before we can route
    // through it; e.g. a cellular NIC may not be IP-configured yet.
    if (!ie->findProtocolDataForUpdate<Ipv4InterfaceData>()) {
        EV_WARN << "Interface '" << ifaceName_[idx] << "' has no IPv4 data yet for RAT "
                << ratName(target) << "; deferring route install." << endl;
        return false;
    }
    // Remove existing default route(s).
    for (int i = rt_->getNumRoutes() - 1; i >= 0; --i) {
        Ipv4Route *r = rt_->getRoute(i);
        if (r->getDestination().isUnspecified() && r->getNetmask().isUnspecified())
            rt_->deleteRoute(r);
    }
    Ipv4Route *nr = new Ipv4Route();
    nr->setDestination(Ipv4Address::UNSPECIFIED_ADDRESS);
    nr->setNetmask(Ipv4Address::UNSPECIFIED_ADDRESS);
    if (!gateway_[idx].empty())
        nr->setGateway(Ipv4Address(gateway_[idx].c_str()));
    nr->setInterface(ie);
    nr->setSourceType(Ipv4Route::MANUAL);
    nr->setMetric(0);
    rt_->addRoute(nr);
    return true;
}

void MultiRatAppManager::handleMessage(cMessage *msg)
{
    if (msg == decisionTimer_) {
        decide();
        scheduleAt(simTime() + decisionInterval_, decisionTimer_);
    }
    else if (msg == applyTimer_) {
        applyHandover();
    }
    else {
        delete msg;
    }
}

void MultiRatAppManager::finish()
{
    accountResidency();

    double total = 0;
    for (int i = 0; i < (int)RatId::COUNT; ++i)
        total += residency_[i];

    for (int i = 0; i < (int)RatId::COUNT; ++i) {
        std::string base = ratName((RatId)i);
        recordScalar((base + ".residencyTime").c_str(), residency_[i], "s");
        recordScalar((base + ".selectionShare").c_str(),
                total > 0 ? residency_[i] / total : 0.0);
    }
    recordScalar("handoversTotal", handoverTotal_);
    recordScalar("pingPongTotal", pingPongTotal_);
    recordScalar("pingPongRatio",
            handoverTotal_ > 0 ? (double)pingPongTotal_ / handoverTotal_ : 0.0);

    // Measured handover-delay summary (mean/max over all completed handovers).
    recordScalar("handoverDelayMean",
            handoverTotal_ > 0 ? handoverDelaySum_ / handoverTotal_ : 0.0, "s");
    recordScalar("handoverDelayMax", handoverDelayMax_, "s");
    recordScalar("handoverDelayTotal", handoverDelaySum_, "s");

    cancelAndDelete(decisionTimer_);
    cancelAndDelete(applyTimer_);
    decisionTimer_ = applyTimer_ = nullptr;
}

} // namespace multiratvanet
