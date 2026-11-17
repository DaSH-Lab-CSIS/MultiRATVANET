//
// MultiRatSink implementation. See MultiRatSink.ned for the module description.
//

#include "MultiRatSink.h"

#include "MultiRatPayload_m.h"

#include "inet/common/TimeTag_m.h"
#include "inet/common/packet/Packet.h"
#include "inet/networklayer/common/L3AddressTag_m.h"
#include "inet/transportlayer/common/L4PortTag_m.h"

namespace multiratvanet {

using namespace omnetpp;
using namespace inet;

Define_Module(MultiRatSink);

MultiRatSink::~MultiRatSink()
{
    cancelAndDelete(replyTimer);
}

void MultiRatSink::initialize(int stage)
{
    ApplicationBase::initialize(stage);

    if (stage == INITSTAGE_LOCAL) {
        deadline = par("deadline");
        packetReceivedSignal = registerSignal("packetReceived");
        replySentSignal = registerSignal("replySent");
        switchInterruptionSignal = registerSignal("switchInterruption");
        switchLossSignal = registerSignal("switchLoss");
        replyTimer = new cMessage("replyDue");
    }
}

void MultiRatSink::handleStartOperation(LifecycleOperation *)
{
    socket.setOutputGate(gate("socketOut"));
    socket.setCallback(this);
    socket.bind(par("localPort").intValue());
}

void MultiRatSink::handleMessageWhenUp(cMessage *msg)
{
    if (msg == replyTimer)
        sendDueReplies();
    else
        socket.processMessage(msg);
}

void MultiRatSink::socketDataArrived(UdpSocket *, Packet *packet)
{
    auto payload = packet->peekAtFront<MultiRatPayload>();
    if (payload->getReply()) {  // not ours
        delete packet;
        return;
    }
    emit(packetReceivedSignal, packet);
    ++received;

    if (deadline > SIMTIME_ZERO && simTime() - payload->getRequestTime() <= deadline)
        ++withinDeadline;
    if (payload->getRat() >= 0 && payload->getRat() < (int)RatId::COUNT)
        ++receivedPerRat[payload->getRat()];

    // First request of a sender's new switch epoch to arrive: the new RAT is now delivering.
    // Measured from the first request the sender put on the new RAT, so idle gaps in the
    // traffic do not count; requests of that epoch sent earlier than this one were lost.
    auto it = lastSwitchCount.find(payload->getCarId());
    if (it == lastSwitchCount.end())
        lastSwitchCount[payload->getCarId()] = payload->getSwitchCount();  // first contact: nothing to measure
    else if (payload->getSwitchCount() > it->second) {
        it->second = payload->getSwitchCount();
        ++switchesMeasured;
        emit(switchInterruptionSignal, (simTime() - payload->getEpochStartTime()).dbl());
        emit(switchLossSignal, payload->getSeq() - payload->getEpochStartSeq());
    }

    // The reply the request asked for goes back to where the request came from: the address of
    // the interface the vehicle sent it on, so it returns over the same RAT.
    if (payload->getReplyCount() > 0) {
        PendingReply r;
        r.addr = packet->getTag<L3AddressInd>()->getSrcAddress();
        r.port = packet->getTag<L4PortInd>()->getSrcPort();
        r.carId = payload->getCarId();
        r.seq = payload->getSeq();
        r.rat = payload->getRat();
        r.requestTime = payload->getRequestTime();
        r.length = payload->getReplyLength();
        for (int i = 0; i < payload->getReplyCount(); ++i) {
            r.index = i;
            pendingReplies.insert({ simTime() + i * payload->getReplyInterval(), r });
        }
        sendDueReplies();
    }
    delete packet;
}

void MultiRatSink::sendDueReplies()
{
    while (!pendingReplies.empty() && pendingReplies.begin()->first <= simTime()) {
        const PendingReply& r = pendingReplies.begin()->second;
        const auto& payload = makeShared<MultiRatPayload>();
        payload->setChunkLength(B(r.length));
        payload->setReply(true);
        payload->setCarId(r.carId);
        payload->setSeq(r.seq);
        payload->setRat(r.rat);
        payload->setRequestTime(r.requestTime);
        payload->setReplyIndex(r.index);
        payload->addTag<CreationTimeTag>()->setCreationTime(simTime());
        auto packet = new Packet("reply", payload);
        emit(replySentSignal, packet);
        socket.sendTo(packet, r.addr, r.port);
        ++repliesSent;
        pendingReplies.erase(pendingReplies.begin());
    }
    cancelEvent(replyTimer);
    if (!pendingReplies.empty())
        scheduleAt(pendingReplies.begin()->first, replyTimer);
}

void MultiRatSink::finish()
{
    recordScalar("packetsReceived", received);
    recordScalar("packetsWithinDeadline", withinDeadline);
    recordScalar("deadline", deadline.dbl(), "s");
    recordScalar("repliesSent", repliesSent);
    recordScalar("switchesMeasured", switchesMeasured);
    for (int i = 0; i < (int)RatId::COUNT; ++i)
        recordScalar((std::string(ratName((RatId)i)) + ".packetsReceived").c_str(), receivedPerRat[i]);
    ApplicationBase::finish();
}

} // namespace multiratvanet
