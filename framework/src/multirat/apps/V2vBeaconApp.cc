//
// V2vBeaconApp implementation. See V2vBeaconApp.h for the module description.
//

#include "V2vBeaconApp.h"

#include "inet/applications/base/ApplicationPacket_m.h"
#include "inet/common/ModuleAccess.h"
#include "inet/common/TimeTag_m.h"
#include "inet/common/packet/Packet.h"
#include "inet/networklayer/common/L3AddressResolver.h"
#include "inet/networklayer/common/L3AddressTag_m.h"
#include "inet/networklayer/contract/IInterfaceTable.h"
#include "inet/networklayer/contract/ipv4/Ipv4Address.h"
#include "inet/networklayer/ipv4/Ipv4InterfaceData.h"
#include "inet/physicallayer/wireless/common/contract/packetlevel/IRadio.h"

namespace multiratvanet {

using namespace inet;
using namespace inet::physicallayer;

Define_Module(V2vBeaconApp);

V2vBeaconApp::~V2vBeaconApp()
{
    cancelAndDelete(beaconTimer);
    cancelAndDelete(cbrTimer);
}

void V2vBeaconApp::initialize(int stage)
{
    ApplicationBase::initialize(stage);

    if (stage == INITSTAGE_LOCAL) {
        localPort = par("localPort");
        destPort = par("destPort");
        groupAddressStr = par("groupAddress");
        v2vInterfaceName = par("v2vInterface");
        beaconInterval = par("beaconInterval");
        startTime = par("startTime");
        neighborTimeout = par("neighborTimeout").doubleValue();
        cbrWindow = par("cbrWindow").doubleValue();

        beaconSentSignal_ = registerSignal("v2vBeaconSent");
        beaconRcvdSignal_ = registerSignal("v2vBeaconRcvd");
        neighborsSignal_ = registerSignal("v2vNeighbors");
        cbrSignal_ = registerSignal("v2vCbr");

        beaconTimer = new cMessage("v2vBeacon");
        cbrTimer = new cMessage("v2vCbrSample");
    }
}

void V2vBeaconApp::handleStartOperation(LifecycleOperation *)
{
    socket.setOutputGate(gate("socketOut"));
    socket.bind(destPort);   // receive the multicast beacons on the shared port
    socket.setCallback(this);

    // Resolve the dedicated V2V (ad-hoc DSRC) interface and pin egress to it.
    IInterfaceTable *ift = getModuleFromPar<IInterfaceTable>(par("interfaceTableModule"), this);
    NetworkInterface *ie = ift->findInterfaceByName(v2vInterfaceName);
    if (ie == nullptr)
        throw cRuntimeError("V2vBeaconApp: V2V interface '%s' not found", v2vInterfaceName);
    v2vInterfaceId = ie->getInterfaceId();

    // A dynamically-created car is not reached by the global Ipv4NetworkConfigurator,
    // and the per-car HostAutoConfigurator only addresses the cellular interface, so
    // the ad-hoc V2V interface has no IPv4 identity. Give it one on a dedicated V2V
    // subnet so it can source/receive the multicast beacons.
    auto ipv4Data = ie->findProtocolDataForUpdate<Ipv4InterfaceData>();
    if (ipv4Data == nullptr)
        ipv4Data = ie->addProtocolData<Ipv4InterfaceData>();
    if (ipv4Data->getIPAddress().isUnspecified()) {
        Ipv4Address base(par("v2vAddressBase").stringValue());
        uint32_t addr = base.getInt() + (uint32_t)getContainingNode(this)->getId();
        ipv4Data->setIPAddress(Ipv4Address(addr));
        ipv4Data->setNetmask(Ipv4Address(par("v2vNetmask").stringValue()));
        ie->setBroadcast(true);
    }

    L3AddressResolver().tryResolve(groupAddressStr, groupAddr);
    if (groupAddr.isUnspecified())
        throw cRuntimeError("V2vBeaconApp: could not resolve group address '%s'", groupAddressStr);

    socket.setMulticastOutputInterface(v2vInterfaceId);
    socket.joinMulticastGroup(groupAddr, v2vInterfaceId);

    // Subscribe to the V2V radio's medium-state signals to measure CBR.
    radioModule_ = getModuleFromPar<cModule>(par("radioModule"), this);
    radioModule_->subscribe(IRadio::receptionStateChangedSignal, this);
    radioModule_->subscribe(IRadio::transmissionStateChangedSignal, this);
    lastBusyChange = simTime();
    busyAccum = SIMTIME_ZERO;
    totalBusyTime = SIMTIME_ZERO;
    cbrObsStart = simTime();
    scheduleAt(simTime() + cbrWindow, cbrTimer);

    lastSampleTime = simTime().dbl();
    scheduleAt(std::max(startTime, simTime()), beaconTimer);
}

void V2vBeaconApp::handleMessageWhenUp(cMessage *msg)
{
    if (msg == beaconTimer) {
        sampleNeighbors();
        sendBeacon();
        scheduleAt(simTime() + beaconInterval, beaconTimer);
    }
    else if (msg == cbrTimer) {
        accountBusyUpTo(simTime());
        double cbr = cbrWindow > 0 ? busyAccum.dbl() / cbrWindow : 0.0;
        if (cbr > 1.0)
            cbr = 1.0;
        emit(cbrSignal_, cbr);
        if (cbr > maxCbr)
            maxCbr = cbr;
        busyAccum = SIMTIME_ZERO;
        scheduleAt(simTime() + cbrWindow, cbrTimer);
    }
    else {
        socket.processMessage(msg);
    }
}

void V2vBeaconApp::accountBusyUpTo(simtime_t now)
{
    if (channelBusy) {
        simtime_t d = now - lastBusyChange;
        busyAccum += d;
        totalBusyTime += d;
    }
    lastBusyChange = now;
}

void V2vBeaconApp::receiveSignal(cComponent *, simsignal_t signalID, long value, cObject *)
{
    if (signalID == IRadio::receptionStateChangedSignal) {
        accountBusyUpTo(simTime());
        auto state = static_cast<IRadio::ReceptionState>(value);
        rxBusy = (state == IRadio::RECEPTION_STATE_BUSY || state == IRadio::RECEPTION_STATE_RECEIVING);
        channelBusy = rxBusy || txBusy;
    }
    else if (signalID == IRadio::transmissionStateChangedSignal) {
        accountBusyUpTo(simTime());
        auto state = static_cast<IRadio::TransmissionState>(value);
        txBusy = (state == IRadio::TRANSMISSION_STATE_TRANSMITTING);
        channelBusy = rxBusy || txBusy;
    }
}

void V2vBeaconApp::sendBeacon()
{
    long beaconBytes = par("beaconBytes");

    Packet *packet = new Packet("v2vBeacon");
    const auto& payload = makeShared<ApplicationPacket>();
    payload->setChunkLength(B(beaconBytes));
    payload->setSequenceNumber(seqNo);
    payload->addTag<CreationTimeTag>()->setCreationTime(simTime());
    packet->insertAtBack(payload);

    emit(beaconSentSignal_, packet);
    socket.sendTo(packet, groupAddr, destPort);
    seqNo++;
    beaconsSent++;
}

void V2vBeaconApp::socketDataArrived(UdpSocket *, Packet *packet)
{
    processBeacon(packet);
}

void V2vBeaconApp::processBeacon(Packet *packet)
{
    // dataAge(v2vBeaconRcvd) yields the one-way inter-vehicle beacon delay.
    emit(beaconRcvdSignal_, packet);

    L3Address src;
    if (auto addrTag = packet->findTag<L3AddressInd>())
        src = addrTag->getSrcAddress();

    long seq = -1;
    if (const auto& appPk = packet->peekAtFront<ApplicationPacket>(B(0), Chunk::PF_ALLOW_NULLPTR))
        seq = appPk->getSequenceNumber();

    if (!src.isUnspecified()) {
        SenderRec &rec = senders[src];
        if (rec.firstSeq < 0)
            rec.firstSeq = seq;
        if (seq > rec.lastSeq)
            rec.lastSeq = seq;
        rec.count++;
        rec.lastSeen = simTime().dbl();
    }

    beaconsReceived++;
    delete packet;
}

long V2vBeaconApp::sampleNeighbors()
{
    double now = simTime().dbl();
    long neighbors = 0;
    for (auto &kv : senders)
        if (now - kv.second.lastSeen <= neighborTimeout)
            ++neighbors;

    double dt = now - lastSampleTime;
    if (dt > 0) {
        neighborIntegral += (double)neighbors * dt;
        sampledTime += dt;
    }
    lastSampleTime = now;
    if (neighbors > maxNeighbors)
        maxNeighbors = neighbors;

    emit(neighborsSignal_, neighbors);
    return neighbors;
}

void V2vBeaconApp::socketErrorArrived(UdpSocket *, Indication *indication)
{
    EV_WARN << "V2vBeaconApp: ignoring UDP error indication " << indication->getName() << "\n";
    delete indication;
}

void V2vBeaconApp::socketClosed(UdpSocket *)
{
    if (operationalState == State::STOPPING_OPERATION)
        startActiveOperationExtraTimeOrFinish(par("stopOperationExtraTime"));
}

void V2vBeaconApp::handleStopOperation(LifecycleOperation *)
{
    cancelEvent(beaconTimer);
    cancelEvent(cbrTimer);
    if (radioModule_) {
        radioModule_->unsubscribe(IRadio::receptionStateChangedSignal, this);
        radioModule_->unsubscribe(IRadio::transmissionStateChangedSignal, this);
        radioModule_ = nullptr;
    }
    socket.close();
    delayActiveOperationFinish(par("stopOperationTimeout"));
}

void V2vBeaconApp::handleCrashOperation(LifecycleOperation *)
{
    cancelEvent(beaconTimer);
    cancelEvent(cbrTimer);
    if (radioModule_) {
        radioModule_->unsubscribe(IRadio::receptionStateChangedSignal, this);
        radioModule_->unsubscribe(IRadio::transmissionStateChangedSignal, this);
        radioModule_ = nullptr;
    }
    socket.destroy();
}

void V2vBeaconApp::finish()
{
    // Fold the final interval into the neighbour accounting.
    double now = simTime().dbl();
    double dt = now - lastSampleTime;
    if (dt > 0) {
        long neighbors = 0;
        for (auto &kv : senders)
            if (now - kv.second.lastSeen <= neighborTimeout)
                ++neighbors;
        neighborIntegral += (double)neighbors * dt;
        sampledTime += dt;
    }

    // Mean beacon reception ratio across all senders that sent >1 beacon.
    double pdrSum = 0.0;
    int nSenders = 0;
    for (auto &kv : senders) {
        long expected = kv.second.lastSeq - kv.second.firstSeq + 1;
        if (expected > 0) {
            double pdr = (double)kv.second.count / (double)expected;
            if (pdr > 1.0)
                pdr = 1.0;
            pdrSum += pdr;
            ++nSenders;
        }
    }

    recordScalar("v2vBeaconsSent", beaconsSent);
    recordScalar("v2vBeaconsReceived", beaconsReceived);
    recordScalar("v2vMeanPdr", nSenders > 0 ? pdrSum / nSenders : 0.0);
    recordScalar("v2vAvgNeighbors", sampledTime > 0 ? neighborIntegral / sampledTime : 0.0);
    recordScalar("v2vMaxNeighbors", maxNeighbors);
    recordScalar("v2vDistinctNeighbors", (long)senders.size());

    // Channel Busy Ratio: overall busy fraction + peak per-window value.
    accountBusyUpTo(simTime());
    double obs = (simTime() - cbrObsStart).dbl();
    recordScalar("v2vMeanCbr", obs > 0 ? totalBusyTime.dbl() / obs : 0.0);
    recordScalar("v2vMaxCbr", maxCbr);

    ApplicationBase::finish();
}

} // namespace multiratvanet
