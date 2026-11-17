//
// MultiRatAppManager.cc
//
#include "MultiRatAppManager.h"

#include <cmath>
#include <cstdio>

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
#include "inet/mobility/contract/IMobility.h"
#include "inet/networklayer/common/L3AddressResolver.h"

#include "veins_inet/VeinsInetMobility.h"

namespace multiratvanet {

using namespace omnetpp;
using namespace inet;

Define_Module(MultiRatAppManager);

// One decision log per run, shared by every car: opened by the first car that decides, closed
// when the last car is gone.
static std::shared_ptr<std::ofstream> openDecisionLog(const std::string &path, const RatMetricsVec &metrics)
{
    static std::map<std::string, std::weak_ptr<std::ofstream>> open;
    if (auto f = open[path].lock())
        return f;
    auto f = std::make_shared<std::ofstream>(path, std::ios::trunc);
    if (!*f)
        throw cRuntimeError("cannot write decision log '%s'", path.c_str());
    // per RAT: usable, SINR margin (dB above the RAT's minimum), sensed load, link rate (Mbit/s),
    // mean probe round trip (ms), serving RSU/AP/cell
    *f << "t,car,x,y,current,choice,branch,detail";
    for (const auto &m : metrics)
        if (m.present) {
            std::string r = ratName(m.id);
            *f << ',' << r << "_ok," << r << "_sinr," << r << "_load," << r << "_rate," << r << "_rtt," << r << "_via";
        }
    *f << '\n';
    open[path] = f;
    return f;
}

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

        PolicyParams pp;
        pp.timeToTrigger = par("timeToTrigger").doubleValue();
        pp.sinrMarginDb = par("sinrSwitchMargin").doubleValue();
        pp.loadMargin = par("loadSwitchMargin").doubleValue();
        pp.maxLatencyMs = par("latencyBudget").doubleValue() * 1e3;
        policy_ = RatPolicyFactory::create(par("policy").stdstringValue(), pp);
        if (!policy_)
            throw cRuntimeError("Unknown policy \"%s\" (CoveragePriority, Sinr, LatencyQos, Load, Ml, Ensemble, ExampleSplit, OnlyDsrc, OnlyWifi or OnlyNr)",
                    par("policy").stringValue());
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
        decisionRejectedSignal_ = registerSignal("decisionRejected");

        // who this vehicle is, for the policy
        cModule *host = getContainingNode(this);
        vehicleId_ = host->isVector() ? host->getIndex() : host->getId();
        cModule *mob = host->getSubmodule("mobility");
        mobility_ = dynamic_cast<IMobility *>(mob);
        if (auto *sumoMobility = dynamic_cast<veins::VeinsInetMobility *>(mob))
            externalId_ = sumoMobility->getExternalId();

        decisionTimer_ = new cMessage("ratDecision");
        applyTimer_ = new cMessage("applyHandover");
        // Random phase within one decision interval: cars appear on SUMO's time grid, and
        // decisions in lockstep would make every car switch (and ARP, and associate) at the
        // same instant, which real cars do not.
        scheduleAt(simTime() + par("startTime").doubleValue() + uniform(0, decisionInterval_), decisionTimer_);
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
    // One /8 block per WiFi/DSRC RAT (DSRC 30.x, WiFi 20.x; 10.x is the cellular network),
    // <block>.<hi>.<lo>.1 with a 16-bit number per car. The router has a route for each block
    // onto that RAT's LAN (simulations/router.mrt), so the server's replies find their way back. Cars are
    // elements of one module vector whose index is never reused, so the index is unique; the
    // module id is not (it grows by several hundred per car and would wrap within one long run).
    cModule *host = getContainingNode(this);
    uint32_t hostId = (uint32_t)(host->isVector() ? host->getIndex() : host->getId());
    if (hostId > 0xFFFF)
        throw cRuntimeError("Cannot give %s a unique DSRC/WiFi address: more than 65536 vehicles in one run",
                host->getFullPath().c_str());
    const struct { RatId id; uint8_t block; } wlans[] = {
        { RatId::DSRC, 30 }, { RatId::WIFI, 20 }
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

    emit(decisionCountSignal_, (long)1);
    RatId before = current_;
    PolicyResponse response = policy_->decide(buildRequest());
    if (!par("decisionLog").stdstringValue().empty())
        logDecision(before, response, metrics);
    RatId target = response.rat;
    previous_.requestedRat = target;
    if (!response.reason.empty())
        EV_INFO << policy_->name() << ": " << ratName(target) << " (" << response.reason << ")" << endl;

    applyDefaultRat(target, metrics);

    // A RAT of its own for a traffic class, if the policy named one that is in range.
    for (auto &entry : classes_) {
        RatId own = RatId::NONE;
        auto it = response.classRat.find(entry.first);
        if (it != response.classRat.end() && it->second != RatId::NONE) {
            if (IRatSelectionPolicy::usable(it->second, metrics))
                own = it->second;
            else {
                emit(decisionRejectedSignal_, (long)1);
                EV_WARN << policy_->name() << " asked for " << ratName(it->second) << " for class " << entry.first
                        << ", which is not in range; the class stays on the default RAT." << endl;
            }
        }
        entry.second.overrideRat = own;
    }
    updateClassRats();
}

// One row per decision: where the car was, what each RAT measured, what the policy chose and why.
void MultiRatAppManager::logDecision(RatId before, const PolicyResponse &response, const RatMetricsVec &metrics)
{
    if (!decisionLog_)
        decisionLog_ = openDecisionLog(par("decisionLog").stdstringValue(), metrics);
    double x = NAN, y = NAN;
    monitor_->getPosition(x, y);
    auto rat = [](RatId r) { return r == RatId::NONE ? "" : ratName(r); };
    std::string detail = response.reason;
    for (char &ch : detail)
        if (ch == ',' || ch == '\n') ch = ';';
    std::ofstream &f = *decisionLog_;
    char buf[200];
    snprintf(buf, sizeof buf, "%.3f,%d,%.1f,%.1f,%s,%s,%s,", simTime().dbl(), getContainingNode(this)->getIndex(), x, y,
             rat(before), rat(response.rat), response.branch.c_str());
    f << buf << detail;
    auto num = [&](double v, const char *fmt) { if (std::isnan(v)) return std::string(); snprintf(buf, sizeof buf, fmt, v); return std::string(buf); };
    for (const auto &m : metrics) {
        if (!m.present)
            continue;
        bool measured = m.measurementAge >= 0 && m.sinrDb > -49.9;  // -50 = no fresh measurement
        f << ',' << (m.inRange ? 1 : 0)
          << ',' << (measured ? num(m.sinrDb - m.minSinrDb, "%.1f") : "")
          << ',' << num(m.load, "%.3f")
          << ',' << (m.linkRateMbps > 0 ? num(m.linkRateMbps, "%.2f") : "")
          << ',' << num(m.probeRttMeanMs, "%.2f")
          << ',' << monitor_->servingNodeName(m.id);
    }
    f << '\n';
}

void MultiRatAppManager::applyDefaultRat(RatId target, const RatMetricsVec &metrics)
{
    if (target == RatId::NONE || target == current_) {
        previous_.outcome = DecisionOutcome::KEPT; // no usable RAT, or stay: keep whatever we had
        return;
    }
    // A policy must only name a RAT that is in range. The built-in ones always do.
    if (!IRatSelectionPolicy::usable(target, metrics)) {
        previous_.outcome = DecisionOutcome::REJECTED;
        emit(decisionRejectedSignal_, (long)1);
        EV_WARN << policy_->name() << " asked for " << ratName(target) << ", which is not in range; ignored." << endl;
        return;
    }

    if (current_ == RatId::NONE) {
        attach(target);
    }
    else if (!inHandover_) {
        previous_.outcome = DecisionOutcome::SWITCH_PENDING; // applyHandover() settles it
        initiateHandover(target);
    }
    else {
        previous_.outcome = DecisionOutcome::IGNORED;
    }
}

void MultiRatAppManager::updateClassRats()
{
    double now = simTime().dbl();
    for (auto &entry : classes_) {
        ClassState &c = entry.second;
        RatId rat = c.overrideRat != RatId::NONE ? c.overrideRat : current_;
        if (rat == c.rat)
            continue;
        if (c.rat != RatId::NONE) {
            c.residency[ratIndex(c.rat)] += now - c.since;
            ++c.switches;
        }
        c.rat = rat;
        c.since = now;
    }
}

void MultiRatAppManager::registerTrafficClass(const std::string &trafficClass)
{
    Enter_Method_Silent();
    ClassState &c = classes_[trafficClass];
    c.rat = current_;
    c.since = simTime().dbl();
}

RatId MultiRatAppManager::getClassRat(const std::string &trafficClass) const
{
    auto it = classes_.find(trafficClass);
    return it == classes_.end() ? current_ : it->second.rat;
}

long MultiRatAppManager::getClassSwitchCount(const std::string &trafficClass) const
{
    auto it = classes_.find(trafficClass);
    return it == classes_.end() ? handoverTotal_ : it->second.switches;
}

bool MultiRatAppManager::getRatRoute(RatId rat, int &interfaceId, Ipv4Address &gateway) const
{
    int idx = ratIndex(rat);
    if (!ift_ || idx < 0 || idx >= (int)RatId::COUNT)
        return false;
    NetworkInterface *ie = ift_->findInterfaceByName(ifaceName_[idx].c_str());
    if (!ie || !ie->findProtocolData<Ipv4InterfaceData>())
        return false;
    interfaceId = ie->getInterfaceId();
    gateway = gatewayOf(idx);
    return true;
}

// The configured gateway of a RAT: an address, or a module and interface ("router%eth0") whose
// address is looked up now, when the network's addresses have been assigned.
Ipv4Address MultiRatAppManager::gatewayOf(int idx) const
{
    if (gateway_[idx].empty())
        return Ipv4Address();
    return L3AddressResolver().resolve(gateway_[idx].c_str(), L3AddressResolver::ADDR_IPv4).toIpv4();
}

void MultiRatAppManager::reportRequest(const std::string &trafficClass, int repliesExpected)
{
    Enter_Method_Silent();
    ClassState &c = classes_[trafficClass];
    for (TrafficCounters *t : { &c.window, &c.total }) {
        ++t->requests;
        t->repliesExpected += repliesExpected;
    }
}

void MultiRatAppManager::reportReply(const std::string &trafficClass, double delay)
{
    Enter_Method_Silent();
    ClassState &c = classes_[trafficClass];
    for (TrafficCounters *t : { &c.window, &c.total }) {
        ++t->repliesReceived;
        t->delaySum += delay;
        if (delay > t->delayMax)
            t->delayMax = delay;
    }
}

PolicyRequest MultiRatAppManager::buildRequest()
{
    PolicyRequest r;
    double now = simTime().dbl();
    r.sequence = requestSeq_++;
    r.time = now;
    r.decisionInterval = decisionInterval_;

    r.vehicle.id = vehicleId_;
    r.vehicle.externalId = externalId_;
    if (mobility_) {
        const Coord &p = mobility_->getCurrentPosition();
        const Coord &v = mobility_->getCurrentVelocity();
        r.vehicle.x = p.x;
        r.vehicle.y = p.y;
        r.vehicle.z = p.z;
        r.vehicle.vx = v.x;
        r.vehicle.vy = v.y;
        r.vehicle.speed = v.length();
        r.vehicle.heading = r.vehicle.speed > 0 ? std::atan2(v.y, v.x) : 0.0;
    }

    r.connection.currentRat = current_;
    r.connection.previousRat = lastRat_;
    r.connection.timeOnCurrentRat = current_ != RatId::NONE ? now - currentSince_ : 0.0;
    r.connection.switchCount = handoverTotal_;
    r.connection.pingPongCount = pingPongTotal_;
    r.connection.switchInProgress = inHandover_;
    r.connection.pendingRat = inHandover_ ? pendingTarget_ : RatId::NONE;

    r.rats = monitor_->getMetrics();
    r.previous = previous_;

    for (auto &entry : classes_) {
        ClassState &c = entry.second;
        TrafficState t;
        t.trafficClass = entry.first;
        t.rat = c.rat;
        t.switchCount = c.switches;
        t.window = c.window;
        t.total = c.total;
        r.traffic.push_back(t);
        c.window = TrafficCounters(); // the next window starts here
    }
    return r;
}

void MultiRatAppManager::attach(RatId target)
{
    if (!applyDefaultRoute(target)) {
        previous_.outcome = DecisionOutcome::SWITCH_FAILED;
        emit(handoverFailedSignal_, (long)1);
        return;
    }
    previous_.outcome = DecisionOutcome::ATTACHED;
    accountResidency();
    lastRat_ = current_;
    current_ = target;
    lastSwitchTime_ = simTime().dbl();
    updateClassRats();
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
        previous_.outcome = DecisionOutcome::SWITCH_FAILED;
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
    previous_.outcome = DecisionOutcome::SWITCH_COMPLETED;
    updateClassRats();

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
    nr->setGateway(gatewayOf(idx));
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
    // the vehicle is leaving (or the run is over): the policy is told, with its last state
    if (policy_ && monitor_)
        policy_->vehicleLeft(buildRequest());

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
    // per traffic class: where it was sent and how often that changed
    for (auto &entry : classes_) {
        ClassState &c = entry.second;
        if (c.rat != RatId::NONE)
            c.residency[ratIndex(c.rat)] += simTime().dbl() - c.since;
        c.since = simTime().dbl();
        double classTotal = 0;
        for (int i = 0; i < (int)RatId::COUNT; ++i)
            classTotal += c.residency[i];
        recordScalar((entry.first + ".switches").c_str(), c.switches);
        for (int i = 0; i < (int)RatId::COUNT; ++i)
            recordScalar((entry.first + "." + ratName((RatId)i) + ".selectionShare").c_str(),
                    classTotal > 0 ? c.residency[i] / classTotal : 0.0);
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

}

MultiRatAppManager::~MultiRatAppManager()
{
    cancelAndDelete(decisionTimer_);
    cancelAndDelete(applyTimer_);
}

} // namespace multiratvanet
