//
// MultiRatTrafficApp implementation. See MultiRatTrafficApp.ned for the module description.
//

#include "MultiRatTrafficApp.h"

#include "MultiRatPayload_m.h"
#include "manager/MultiRatAppManager.h"

#include "inet/common/ModuleAccess.h"
#include "inet/common/TimeTag_m.h"
#include "inet/common/packet/Packet.h"
#include "inet/networklayer/common/L3AddressResolver.h"

namespace multiratvanet {

using namespace omnetpp;
using namespace inet;

Define_Module(MultiRatTrafficApp);

MultiRatTrafficApp::~MultiRatTrafficApp()
{
    cancelAndDelete(sendTimer);
}

void MultiRatTrafficApp::initialize(int stage)
{
    ApplicationBase::initialize(stage);

    if (stage == INITSTAGE_LOCAL) {
        onOff = std::string(par("mode").stringValue()) == "onoff";
        destPort = par("destPort");
        startTime = par("startTime");
        stopTime = par("stopTime");
        if (stopTime >= SIMTIME_ZERO && stopTime < startTime)
            throw cRuntimeError("Invalid startTime/stopTime parameters");
        manager = dynamic_cast<MultiRatAppManager *>(getModuleByPath(par("managerModule").stringValue()));
        packetSentSignal = registerSignal("packetSent");
        sendTimer = new cMessage("trafficSend");
    }
}

void MultiRatTrafficApp::handleStartOperation(LifecycleOperation *)
{
    socket.setOutputGate(gate("socketOut"));
    socket.setCallback(this);
    socket.bind(L3Address(), par("localPort"));

    // random phase within one send interval, so cars that appear on the same SUMO time step
    // do not transmit in lockstep
    simtime_t start = std::max(startTime, simTime()) + uniform(0, par("sendInterval").doubleValue());
    if (stopTime < SIMTIME_ZERO || start < stopTime) {
        burstEnd = start + (onOff ? par("onTime").doubleValue() : 0);
        scheduleAt(start, sendTimer);
    }
}

void MultiRatTrafficApp::handleStopOperation(LifecycleOperation *)
{
    cancelEvent(sendTimer);
    socket.close();
}

void MultiRatTrafficApp::handleCrashOperation(LifecycleOperation *)
{
    cancelEvent(sendTimer);
    socket.destroy();
}

void MultiRatTrafficApp::handleMessageWhenUp(cMessage *msg)
{
    if (msg == sendTimer) {
        sendPacket();
        scheduleNext();
    }
    else
        socket.processMessage(msg);
}

void MultiRatTrafficApp::scheduleNext()
{
    simtime_t next = simTime() + par("sendInterval").doubleValue();
    if (onOff && next >= burstEnd) {
        // "on" period over: stay silent for offTime, then start the next burst
        simtime_t burstStart = burstEnd + par("offTime").doubleValue();
        burstEnd = burstStart + par("onTime").doubleValue();
        next = burstStart;
    }
    if (stopTime < SIMTIME_ZERO || next < stopTime)
        scheduleAt(next, sendTimer);
}

void MultiRatTrafficApp::sendPacket()
{
    if (destAddr.isUnspecified())
        destAddr = L3AddressResolver().resolve(par("destAddress"));

    RatId rat = manager ? manager->getActiveRat() : RatId::NONE;
    long switches = manager ? manager->getSwitchCount() : 0;
    if (switches != epochSwitchCount) {
        // first packet since the sender's latest switch (or its very first packet)
        epochSwitchCount = switches;
        epochStartSeq = seq;
        epochStartTime = simTime();
    }

    const auto& payload = makeShared<MultiRatPayload>();
    payload->setChunkLength(B(par("messageLength")));
    payload->setCarId(getContainingNode(this)->getId());
    payload->setSeq(seq);
    payload->setRat((int)rat);
    payload->setSwitchCount(switches);
    payload->setEpochStartSeq(epochStartSeq);
    payload->setEpochStartTime(epochStartTime);
    payload->addTag<CreationTimeTag>()->setCreationTime(simTime());

    std::ostringstream name;
    name << par("trafficClass").stringValue() << "-" << seq;
    auto packet = new Packet(name.str().c_str(), payload);
    emit(packetSentSignal, packet);
    socket.sendTo(packet, destAddr, destPort);

    ++seq;
    if (rat == RatId::NONE)
        ++sentNoRat;
    else
        ++sentPerRat[ratIndex(rat)];
}

void MultiRatTrafficApp::finish()
{
    for (int i = 0; i < (int)RatId::COUNT; ++i)
        recordScalar((std::string(ratName((RatId)i)) + ".packetsSent").c_str(), sentPerRat[i]);
    recordScalar("NONE.packetsSent", sentNoRat);
    ApplicationBase::finish();
}

} // namespace multiratvanet
