//
// MultiRatSink implementation. See MultiRatSink.ned for the module description.
//

#include "MultiRatSink.h"

#include "MultiRatPayload_m.h"

#include "inet/common/TimeTag_m.h"
#include "inet/common/packet/Packet.h"

namespace multiratvanet {

using namespace omnetpp;
using namespace inet;

Define_Module(MultiRatSink);

void MultiRatSink::initialize(int stage)
{
    ApplicationBase::initialize(stage);

    if (stage == INITSTAGE_LOCAL) {
        deadline = par("deadline");
        packetReceivedSignal = registerSignal("packetReceived");
        switchInterruptionSignal = registerSignal("switchInterruption");
        switchLossSignal = registerSignal("switchLoss");
    }
}

void MultiRatSink::handleStartOperation(LifecycleOperation *)
{
    socket.setOutputGate(gate("socketOut"));
    socket.setCallback(this);
    socket.bind(par("localPort").intValue());
}

void MultiRatSink::socketDataArrived(UdpSocket *, Packet *packet)
{
    emit(packetReceivedSignal, packet);
    ++received;

    auto payload = packet->peekAtFront<MultiRatPayload>();
    simtime_t sent = SIMTIME_ZERO;
    for (auto& region : payload->getAllTags<CreationTimeTag>())
        sent = region.getTag()->getCreationTime();
    if (deadline > SIMTIME_ZERO && simTime() - sent <= deadline)
        ++withinDeadline;
    if (payload->getRat() >= 0 && payload->getRat() < (int)RatId::COUNT)
        ++receivedPerRat[payload->getRat()];

    // First packet of a sender's new switch epoch to arrive: the new RAT is now delivering.
    // Measured from the first packet the sender put on the new RAT, so idle gaps in the
    // traffic do not count; packets of that epoch sent earlier than this one were lost.
    auto it = lastSwitchCount.find(payload->getCarId());
    if (it == lastSwitchCount.end())
        lastSwitchCount[payload->getCarId()] = payload->getSwitchCount();  // first contact: nothing to measure
    else if (payload->getSwitchCount() > it->second) {
        it->second = payload->getSwitchCount();
        ++switchesMeasured;
        emit(switchInterruptionSignal, (simTime() - payload->getEpochStartTime()).dbl());
        emit(switchLossSignal, payload->getSeq() - payload->getEpochStartSeq());
    }
    delete packet;
}

void MultiRatSink::finish()
{
    recordScalar("packetsReceived", received);
    recordScalar("packetsWithinDeadline", withinDeadline);
    recordScalar("deadline", deadline.dbl(), "s");
    recordScalar("switchesMeasured", switchesMeasured);
    for (int i = 0; i < (int)RatId::COUNT; ++i)
        recordScalar((std::string(ratName((RatId)i)) + ".packetsReceived").c_str(), receivedPerRat[i]);
    ApplicationBase::finish();
}

} // namespace multiratvanet
