//
// MultiRatTrafficApp implementation. See MultiRatTrafficApp.ned for the module description.
//

#include "MultiRatTrafficApp.h"

#include "MultiRatPayload_m.h"
#include "manager/MultiRatAppManager.h"

#include "inet/common/ModuleAccess.h"
#include "inet/common/TimeTag_m.h"
#include "inet/common/packet/Packet.h"
#include "inet/linklayer/common/InterfaceTag_m.h"
#include "inet/networklayer/common/L3AddressResolver.h"
#include "inet/networklayer/common/NextHopAddressTag_m.h"
#include "inet/networklayer/contract/ipv4/Ipv4Address.h"

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
        replyCount = par("replyCount");
        deadline = par("deadline");
        trafficClass = par("trafficClass").stdstringValue();
        startTime = par("startTime");
        stopTime = par("stopTime");
        if (stopTime >= SIMTIME_ZERO && stopTime < startTime)
            throw cRuntimeError("Invalid startTime/stopTime parameters");
        // "" = no manager (packets are then recorded as sent on no RAT); anything else must resolve
        if (!par("managerModule").stdstringValue().empty())
            manager = check_and_cast<MultiRatAppManager *>(getModuleByPath(par("managerModule").stringValue()));
        if (manager)
            manager->registerTrafficClass(trafficClass);
        packetSentSignal = registerSignal("packetSent");
        replyReceivedSignal = registerSignal("replyReceived");
        replyDelaySignal = registerSignal("replyDelay");
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

    // the RAT the policy chose for this traffic class
    RatId rat = manager ? manager->getClassRat(trafficClass) : RatId::NONE;
    long switches = manager ? manager->getClassSwitchCount(trafficClass) : 0;
    if (switches != epochSwitchCount) {
        // first request since the class's latest switch (or its very first request)
        epochSwitchCount = switches;
        epochStartSeq = seq;
        epochStartTime = simTime();
    }

    const auto& payload = makeShared<MultiRatPayload>();
    payload->setChunkLength(B(par("messageLength")));
    payload->setCarId(getContainingNode(this)->getId());
    payload->setSeq(seq);
    payload->setRat((int)rat);
    payload->setRequestTime(simTime());
    payload->setReplyCount(replyCount);
    if (replyCount > 0) {
        payload->setReplyLength(par("replyLength").intValue());
        payload->setReplyInterval(par("replyInterval").doubleValue());
    }
    payload->setSwitchCount(switches);
    payload->setEpochStartSeq(epochStartSeq);
    payload->setEpochStartTime(epochStartTime);
    payload->addTag<CreationTimeTag>()->setCreationTime(simTime());

    std::ostringstream name;
    name << trafficClass << "-" << seq;
    auto packet = new Packet(name.str().c_str(), payload);

    // The default route carries the vehicle's default RAT. A class the policy put on another
    // RAT is sent out of that RAT's interface explicitly.
    if (manager && rat != RatId::NONE && rat != manager->getActiveRat()) {
        int interfaceId = -1;
        Ipv4Address gateway;
        if (manager->getRatRoute(rat, interfaceId, gateway)) {
            packet->addTag<InterfaceReq>()->setInterfaceId(interfaceId);
            if (!gateway.isUnspecified())
                packet->addTag<NextHopAddressReq>()->setNextHopAddress(gateway);
        }
    }
    emit(packetSentSignal, packet);
    socket.sendTo(packet, destAddr, destPort);

    ++seq;
    repliesExpected += replyCount;
    if (manager)
        manager->reportRequest(trafficClass, replyCount);
    if (rat == RatId::NONE)
        ++sentNoRat;
    else
        ++sentPerRat[ratIndex(rat)];
}

// A reply from the server: for the car, the only sign of how the class is doing.
void MultiRatTrafficApp::socketDataArrived(UdpSocket *, Packet *packet)
{
    auto payload = packet->peekAtFront<MultiRatPayload>();
    if (payload->getReply()) {
        simtime_t delay = simTime() - payload->getRequestTime();
        ++repliesReceived;
        if (deadline > SIMTIME_ZERO && delay <= deadline)
            ++repliesWithinDeadline;
        emit(replyReceivedSignal, packet);
        emit(replyDelaySignal, delay.dbl());
        if (manager)
            manager->reportReply(trafficClass, delay.dbl());
    }
    delete packet;
}

void MultiRatTrafficApp::finish()
{
    for (int i = 0; i < (int)RatId::COUNT; ++i)
        recordScalar((std::string(ratName((RatId)i)) + ".packetsSent").c_str(), sentPerRat[i]);
    recordScalar("NONE.packetsSent", sentNoRat);
    recordScalar("repliesExpected", repliesExpected);
    recordScalar("repliesReceived", repliesReceived);
    recordScalar("repliesWithinDeadline", repliesWithinDeadline);
    recordScalar("replyDeadline", deadline.dbl(), "s");
    ApplicationBase::finish();
}

} // namespace multiratvanet
