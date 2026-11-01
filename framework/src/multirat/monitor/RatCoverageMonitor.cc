//
// RatCoverageMonitor.cc
//
#include "RatCoverageMonitor.h"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <typeinfo>

#include "inet/mobility/contract/IMobility.h"
#include "inet/common/geometry/common/Coord.h"
#include "inet/common/ModuleAccess.h"
#include "inet/common/Simsignals.h"
#include "inet/physicallayer/wireless/common/contract/packetlevel/IRadio.h"
#include "inet/physicallayer/wireless/common/contract/packetlevel/IRadioMedium.h"
#include "inet/physicallayer/wireless/common/contract/packetlevel/IReception.h"
#include "inet/physicallayer/wireless/common/contract/packetlevel/IScalarSignalAnalogModel.h"
#include "inet/physicallayer/wireless/common/contract/packetlevel/ISnir.h"
#include "inet/physicallayer/wireless/common/contract/packetlevel/ITransmission.h"
#include "inet/physicallayer/wireless/ieee80211/mode/Ieee80211ModeSet.h"
#include "inet/linklayer/ieee80211/mib/Ieee80211Mib.h"
#include "inet/networklayer/common/NetworkInterface.h"

#include "simu5g/common/binder/Binder.h"
#include "simu5g/common/cellInfo/CellInfo.h"

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

    const std::string source = par("signalSource").stdstringValue();
    if (source != "measured" && source != "proxy")
        throw cRuntimeError("signalSource must be \"measured\" or \"proxy\", got \"%s\"", source.c_str());
    measuredMode_ = (source == "measured");
    measurementMaxAge_ = par("measurementMaxAge").doubleValue();
    inRangeHysteresisDb_ = par("inRangeHysteresis").doubleValue();
    filterWeight_ = par("filterWeight").doubleValue();
    refPacketBits_ = par("latencyReferencePacket").intValue() * 8.0;
    for (int i = 0; i < (int)RatId::COUNT; ++i) {
        minSinrDb_[i] = -1e9;
        pathLatencyMs_[i] = 0;
        uplinkOffsetDb_[i] = 0;
        linkRateMbps_[i] = 0;
    }
    minSinrDb_[(int)RatId::DSRC] = par("dsrcMinSinr").doubleValue();
    minSinrDb_[(int)RatId::WIFI] = par("wifiMinSinr").doubleValue();
    minSinrDb_[(int)RatId::LTE] = par("lteMinSinr").doubleValue();
    minSinrDb_[(int)RatId::NR] = par("nrMinSinr").doubleValue();
    pathLatencyMs_[(int)RatId::DSRC] = pathLatencyMs_[(int)RatId::WIFI] = par("wlanPathLatency").doubleValue() * 1e3;
    pathLatencyMs_[(int)RatId::LTE] = pathLatencyMs_[(int)RatId::NR] = par("cellularPathLatency").doubleValue() * 1e3;
    dsrcNic_ = par("dsrcNic").stdstringValue();
    wifiNic_ = par("wifiNic").stdstringValue();
    for (int i = 0; i < (int)RatId::COUNT; ++i)
        metrics_[i].minSinrDb = minSinrDb_[i];
    if (measuredMode_ && car) {
        // 802.11 link rate: with no rate control configured, INET sends data frames at the
        // fastest mandatory rate of the radio's mode set (RateSelection), so that is the rate.
        for (int rat : { (int)RatId::DSRC, (int)RatId::WIFI }) {
            const std::string &nicName = rat == (int)RatId::DSRC ? dsrcNic_ : wifiNic_;
            cModule *tx = car->findModuleByPath((std::string(".") + nicName + ".radio.transmitter").c_str());
            cModule *rc = car->findModuleByPath((std::string(".") + nicName + ".mac.dcf.rateControl").c_str());
            if (rc && rc->getComponentType())
                throw cRuntimeError("signalSource=\"measured\" assumes no 802.11 rate control on %s", nicName.c_str());
            if (tx && tx->hasPar("opMode"))
                linkRateMbps_[rat] = inet::physicallayer::Ieee80211ModeSet::getModeSet(tx->par("opMode").stringValue())
                        ->getFastestMandatoryMode()->getDataMode()->getNetBitrate().get() / 1e6;
        }
        binder_ = getSimulation()->getSystemModule()->getSubmodule("binder");
        // Simu5G reports downlink SINR; the car sends uplink with less power than the cell.
        // Path loss is the same both ways, so uplink SINR ~ downlink SINR - power difference.
        for (int rat : { (int)RatId::LTE, (int)RatId::NR }) {
            cModule *phy = car->findModuleByPath(rat == (int)RatId::NR ? ".cellularNic.nrPhy" : ".cellularNic.phy");
            if (phy && phy->hasPar("eNodeBTxPower") && phy->hasPar("ueTxPower"))
                uplinkOffsetDb_[rat] = phy->par("eNodeBTxPower").doubleValue() - phy->par("ueTxPower").doubleValue();
        }

        // Signals propagate up the module tree: one subscription on the car sees every radio in it.
        measuredSinrDlSignal_ = registerSignal("measuredSinrDl");
        servedBlocksUlSignal_ = registerSignal("avgServedBlocksUl");
        car->subscribe(inet::receptionEndedSignal, this);
        car->subscribe(measuredSinrDlSignal_, this);
        car->subscribe(inet::physicallayer::IRadio::receptionStateChangedSignal, this);
        car->subscribe(inet::physicallayer::IRadio::transmissionStateChangedSignal, this);
        for (simsignal_t s : { inet::l2AssociatedSignal, inet::l2AssociatedNewApSignal, inet::l2AssociatedOldApSignal,
                               inet::l2DisassociatedSignal, inet::l2BeaconLostSignal })
            car->subscribe(s, this);
        // every gNB's uplink scheduler reports its allocated resource blocks each TTI
        getSimulation()->getSystemModule()->subscribe(servedBlocksUlSignal_, this);
        for (auto &b : busy_)
            b.since = b.windowStart = simTime().dbl();
    }

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

        m.distanceToInfra = minDist;
        if (measuredMode_) {
            applyMeasurement(i, m, simTime().dbl());
        }
        else {
            double rssi = proxyRssiDbm(minDist);
            bool distOk = !useDistance_ || (minDist <= cfg_[i].range);
            bool sigOk = !useSignal_ || (rssi >= cfg_[i].rssiThreshold);
            m.inRange = distOk && sigOk && (cfg_[i].infraType.empty() || !infra_[i].empty());
            m.rssiDbm = rssi;
            m.sinrDb = rssi + 100.0; // crude SINR proxy from RSSI (dB above -100 noise floor)
        }
        bool inRange = m.inRange;
        if (minDist < minInfraDist_[i])
            minInfraDist_[i] = minDist;

        emit(inRangeSignal_[i], (long)(inRange ? 1 : 0));
        if (!std::isnan(m.rssiDbm))
            emit(rssiSignal_[i], m.rssiDbm);
        if (inRange)
            ++coverage;
    }
    emit(coverageCountSignal_, coverage);
    servedBlocks_.clear();  // per-refresh window for the cellular load

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

// Turns what was measured since the last refresh into this RAT's metrics (see the class
// comment in the header for what each metric means). Distance plays no part.
void RatCoverageMonitor::applyMeasurement(int i, RatMetrics &m, double now)
{
    Window &w = window_[i];
    Measured &x = measured_[i];
    bool cellular = (i == (int)RatId::LTE || i == (int)RatId::NR);
    auto filter = [this](double prev, double sample, bool first) {
        return first ? sample : filterWeight_ * sample + (1 - filterWeight_) * prev;
    };

    // signal: one sample per refresh (strongest beacon / mean SINR), then a first-order
    // filter like 3GPP layer-3 filtering, so single fades and collisions do not flip decisions
    if (w.n > 0) {
        double sample = cellular ? w.sinrSum / w.n - uplinkOffsetDb_[i] : w.snirOfBest;
        bool first = !x.valid || now - x.time > measurementMaxAge_;
        x.sinrDb = filter(x.sinrDb, sample, first);
        x.rssiDbm = cellular ? NAN : w.bestRssiDbm;
        x.valid = true;
        x.time = now;
        x.samples += w.n;
    }
    w = Window();

    // load: 802.11 channel busy ratio over this refresh; cellular serving-cell utilisation
    double bandwidthMHz = 0;
    if (cellular) {
        if (const cModule *mac = servingCellMac(i, &bandwidthMHz)) {
            auto it = servedBlocks_.find(mac);
            if (it != servedBlocks_.end() && it->second.second > 0 && bandwidthMHz > 0) {
                double numBands = bandwidthMHz / 0.18;
                double util = std::min(1.0, it->second.first / it->second.second / numBands);
                x.load = filter(x.load, util, false);
            }
        }
    }
    else if (cfg_[i].has) {
        accountBusy(i, now);
        Busy &b = busy_[i];
        double span = now - b.windowStart;
        if (span > 0)
            x.load = filter(x.load, std::min(1.0, b.accum / span), false);
        b.accum = 0;
        b.windowStart = now;
    }

    bool fresh = x.valid && now - x.time <= measurementMaxAge_;
    bool linked = cellular || x.associated;
    double threshold = minSinrDb_[i] + (x.inRange ? 0.0 : inRangeHysteresisDb_);
    x.inRange = fresh && linked && (!useSignal_ || x.sinrDb >= threshold);

    double free = std::max(1.0 - x.load, 0.05);
    double linkRateMbps = cellular
            ? std::min(std::log2(1 + std::pow(10.0, x.sinrDb / 10)), 5.55) * bandwidthMHz  // 5.55 b/s/Hz: 64-QAM, highest CQI
            : linkRateMbps_[i];
    m.inRange = x.inRange;
    m.rssiDbm = fresh ? x.rssiDbm : NAN;
    m.sinrDb = fresh ? x.sinrDb : -50.0;
    m.load = x.load;
    m.capacityMbps = fresh ? linkRateMbps * (1 - x.load) : 0;
    // path latency + service time of a reference packet, stretched by the load (M/M/1)
    m.estLatencyMs = (fresh && linkRateMbps > 0)
            ? pathLatencyMs_[i] + refPacketBits_ / (linkRateMbps * 1e6) / free * 1e3
            : 1e6;
    if (m.inRange) {
        InputStats &st = inputStats_[i];
        ++st.n;
        st.sinrMargin += m.sinrDb - m.minSinrDb;
        st.load += m.load;
        st.capacity += m.capacityMbps;
        st.latency += m.estLatencyMs;
    }
}

void RatCoverageMonitor::accountBusy(int i, double now)
{
    Busy &b = busy_[i];
    if (b.rx || b.tx)
        b.accum += now - b.since;
    b.since = now;
}

// The serving cell's MAC module and bandwidth for the car's LTE or NR stack, or nullptr if
// the car is not attached (or this is not a Simu5G network).
const cModule *RatCoverageMonitor::servingCellMac(int rat, double *bandwidthMHz) const
{
    auto *binder = dynamic_cast<simu5g::Binder *>(binder_);
    cModule *car = getParentModule();
    const char *idPar = rat == (int)RatId::NR ? "nrMacNodeId" : "macNodeId";
    if (!binder || !car || !car->hasPar(idPar))
        return nullptr;
    simu5g::MacNodeId ue = simu5g::MacNodeId(car->par(idPar).intValue());
    simu5g::MacNodeId cell = binder->getServingNode(ue);
    if (cell == simu5g::NODEID_NONE)
        return nullptr;
    if (simu5g::CellInfo *ci = binder->getCellInfoByNodeId(cell))
        *bandwidthMHz = ci->getNumBands() * 0.18;  // 180 kHz per resource block (numerology 0)
    return binder->getMacByNodeId(cell);
}

int RatCoverageMonitor::ratOfWlan(const cModule *nic) const
{
    if (!nic)
        return -1;
    const std::string name = nic->getFullName();
    if (name == dsrcNic_)
        return (int)RatId::DSRC;
    if (name == wifiNic_)
        return (int)RatId::WIFI;
    return -1;
}

// 802.11: every reception that ends at one of this car's radios. Only frames sent by this
// RAT's infrastructure (RSU/AP, matched by NED type like the proxy discovery) count;
// frames from other vehicles are ignored.
void RatCoverageMonitor::receiveSignal(cComponent *source, simsignal_t id, cObject *obj, cObject *details)
{
    using namespace inet::physicallayer;
    if (id == inet::l2AssociatedSignal || id == inet::l2AssociatedNewApSignal || id == inet::l2AssociatedOldApSignal
            || id == inet::l2DisassociatedSignal || id == inet::l2BeaconLostSignal) {
        // obj is the NIC whose association changed
        int rat = ratOfWlan(dynamic_cast<cModule *>(obj));
        if (rat >= 0)
            measured_[rat].associated = (id != inet::l2DisassociatedSignal && id != inet::l2BeaconLostSignal);
        return;
    }
    if (id != inet::receptionEndedSignal)
        return;
    auto reception = dynamic_cast<const IReception *>(obj);
    auto receiverModule = dynamic_cast<cModule *>(source);
    if (!reception || !receiverModule)
        return;
    int rat = ratOfWlan(receiverModule->getParentModule());
    if (rat < 0 || !cfg_[rat].has)
        return;
    auto transmission = reception->getTransmission();
    auto medium = transmission->getMedium();
    auto txRadio = medium->getRadio(transmission->getTransmitterRadioId());  // nullptr if that node is gone
    auto txModule = dynamic_cast<const cModule *>(txRadio);
    if (!txModule)
        return;
    const cModule *txNode = inet::findContainingNode(txModule);
    const char *txType = txNode && txNode->getComponentType() ? txNode->getComponentType()->getName() : "";
    if (!icontains(txType, cfg_[rat].infraType))
        return;

    // While associated, the car can only send through its own AP/RSU: ignore the others' beacons.
    auto mib = dynamic_cast<inet::ieee80211::Ieee80211Mib *>(receiverModule->getParentModule()->getSubmodule("mib"));
    auto txIface = dynamic_cast<const inet::NetworkInterface *>(txModule->getParentModule());
    if (mib && mib->bssStationData.isAssociated && txIface && txIface->getMacAddress() != mib->bssData.bssid)
        return;

    auto power = dynamic_cast<const IScalarSignalAnalogModel *>(reception->getAnalogModel());
    if (!power)
        throw cRuntimeError("signalSource=\"measured\" needs a scalar 802.11 radio model (got %s)",
                reception->getAnalogModel() ? typeid(*reception->getAnalogModel()).name() : "none");
    double rssiDbm = 10.0 * std::log10(inet::units::values::mW(power->getPower()).get());
    // Beacons are downlink; the car sends uplink with its own (usually lower) power. Path loss
    // is the same both ways, so the uplink SNIR is about the beacon's minus the power difference.
    auto txPower = [](const cModule *radio) {
        const cModule *tx = radio ? radio->getSubmodule("transmitter") : nullptr;
        return tx && tx->hasPar("power") ? 10.0 * std::log10(tx->par("power").doubleValue() * 1e3) : NAN;
    };
    double offsetDb = txPower(txModule) - txPower(receiverModule);
    double snirDb = 10.0 * std::log10(medium->getSNIR(reception->getReceiverRadio(), transmission)->getMin())
            - (std::isnan(offsetDb) ? 0.0 : offsetDb);
    Window &w = window_[rat];
    ++w.n;
    if (rssiDbm > w.bestRssiDbm) {
        w.bestRssiDbm = rssiDbm;
        w.snirOfBest = snirDb;
    }
}

// Simu5G: downlink SINR measured by the serving cell's feedback computation, emitted by the
// UE's channel model ("nrChannelModel[..]" for NR, "channelModel[..]" for LTE).
void RatCoverageMonitor::receiveSignal(cComponent *source, simsignal_t id, double value, cObject *details)
{
    if (id == servedBlocksUlSignal_) {
        auto &acc = servedBlocks_[dynamic_cast<cModule *>(source)];
        acc.first += value;
        ++acc.second;
        return;
    }
    if (id != measuredSinrDlSignal_)
        return;
    const char *name = source->getName();
    int rat = std::string(name) == "nrChannelModel" ? (int)RatId::NR
            : std::string(name) == "channelModel" ? (int)RatId::LTE : -1;
    if (rat < 0 || !cfg_[rat].has || std::isnan(value))
        return;
    Window &w = window_[rat];
    ++w.n;
    w.sinrSum += value;
}

// 802.11 radio state changes, for the channel busy ratio: busy while receiving or sensing
// energy (BUSY/RECEIVING) or transmitting.
void RatCoverageMonitor::receiveSignal(cComponent *source, simsignal_t id, intval_t value, cObject *details)
{
    using namespace inet::physicallayer;
    bool isRx = id == IRadio::receptionStateChangedSignal;
    if (!isRx && id != IRadio::transmissionStateChangedSignal)
        return;
    auto radio = dynamic_cast<cModule *>(source);
    int rat = radio ? ratOfWlan(radio->getParentModule()) : -1;
    if (rat < 0)
        return;
    accountBusy(rat, simTime().dbl());
    if (isRx)
        busy_[rat].rx = (value == IRadio::RECEPTION_STATE_BUSY || value == IRadio::RECEPTION_STATE_RECEIVING);
    else
        busy_[rat].tx = (value == IRadio::TRANSMISSION_STATE_TRANSMITTING);
}

RatCoverageMonitor::~RatCoverageMonitor()
{
    cModule *system = getSimulation() ? getSimulation()->getSystemModule() : nullptr;
    if (system && servedBlocksUlSignal_ != -1 && system->isSubscribed(servedBlocksUlSignal_, this))
        system->unsubscribe(servedBlocksUlSignal_, this);
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
        if (measuredMode_) {
            recordScalar((base + ".measuredSamples").c_str(), (double)measured_[i].samples);
            const InputStats &st = inputStats_[i];
            if (st.n > 0) {
                recordScalar((base + ".inRangeSinrMargin").c_str(), st.sinrMargin / st.n, "dB");
                recordScalar((base + ".inRangeLoad").c_str(), st.load / st.n);
                recordScalar((base + ".inRangeCapacity").c_str(), st.capacity / st.n, "Mbps");
                recordScalar((base + ".inRangeLatency").c_str(), st.latency / st.n, "ms");
            }
        }
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
