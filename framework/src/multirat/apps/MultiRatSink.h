//
// MultiRatSink - server side of one traffic class (see MultiRatSink.ned).
//
#ifndef MULTIRATVANET_MULTIRATSINK_H
#define MULTIRATVANET_MULTIRATSINK_H

#include <map>
#include "inet/common/INETDefs.h"
#include "inet/applications/base/ApplicationBase.h"
#include "inet/networklayer/common/L3Address.h"
#include "inet/transportlayer/contract/udp/UdpSocket.h"
#include "base/RatTypes.h"

namespace multiratvanet {

class MultiRatSink : public inet::ApplicationBase, public inet::UdpSocket::ICallback
{
  protected:
    // one reply packet waiting for its send time
    struct PendingReply {
        inet::L3Address addr;
        int port;
        int carId;
        long seq;
        int rat;
        omnetpp::simtime_t requestTime;
        int index;
        int length;
    };

    omnetpp::simtime_t deadline;
    inet::UdpSocket socket;
    std::multimap<omnetpp::simtime_t, PendingReply> pendingReplies;
    omnetpp::cMessage *replyTimer = nullptr;

    long received = 0;
    long withinDeadline = 0;
    long repliesSent = 0;
    long receivedPerRat[(int)RatId::COUNT] = {0};
    long switchesMeasured = 0;
    std::map<int, long> lastSwitchCount;   // per sender: switch epoch already measured

    omnetpp::simsignal_t packetReceivedSignal = -1;
    omnetpp::simsignal_t replySentSignal = -1;
    omnetpp::simsignal_t switchInterruptionSignal = -1;
    omnetpp::simsignal_t switchLossSignal = -1;

  protected:
    virtual int numInitStages() const override { return inet::NUM_INIT_STAGES; }
    virtual void initialize(int stage) override;
    virtual void handleMessageWhenUp(omnetpp::cMessage *msg) override;
    virtual void finish() override;

    void sendDueReplies();

    virtual void handleStartOperation(inet::LifecycleOperation *operation) override;
    virtual void handleStopOperation(inet::LifecycleOperation *operation) override { cancelEvent(replyTimer); socket.close(); }
    virtual void handleCrashOperation(inet::LifecycleOperation *operation) override { cancelEvent(replyTimer); socket.destroy(); }

    virtual void socketDataArrived(inet::UdpSocket *socket, inet::Packet *packet) override;
    virtual void socketErrorArrived(inet::UdpSocket *socket, inet::Indication *indication) override { delete indication; }
    virtual void socketClosed(inet::UdpSocket *socket) override {}

  public:
    virtual ~MultiRatSink();
};

} // namespace multiratvanet

#endif
