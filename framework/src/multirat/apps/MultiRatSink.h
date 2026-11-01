//
// MultiRatSink - server side of one traffic class (see MultiRatSink.ned).
//
#ifndef MULTIRATVANET_MULTIRATSINK_H
#define MULTIRATVANET_MULTIRATSINK_H

#include <map>
#include "inet/common/INETDefs.h"
#include "inet/applications/base/ApplicationBase.h"
#include "inet/transportlayer/contract/udp/UdpSocket.h"
#include "base/RatTypes.h"

namespace multiratvanet {

class MultiRatSink : public inet::ApplicationBase, public inet::UdpSocket::ICallback
{
  protected:
    omnetpp::simtime_t deadline;
    inet::UdpSocket socket;

    long received = 0;
    long withinDeadline = 0;
    long receivedPerRat[(int)RatId::COUNT] = {0};
    long switchesMeasured = 0;
    std::map<int, long> lastSwitchCount;   // per sender: switch epoch already measured

    omnetpp::simsignal_t packetReceivedSignal = -1;
    omnetpp::simsignal_t switchInterruptionSignal = -1;
    omnetpp::simsignal_t switchLossSignal = -1;

  protected:
    virtual int numInitStages() const override { return inet::NUM_INIT_STAGES; }
    virtual void initialize(int stage) override;
    virtual void handleMessageWhenUp(omnetpp::cMessage *msg) override { socket.processMessage(msg); }
    virtual void finish() override;

    virtual void handleStartOperation(inet::LifecycleOperation *operation) override;
    virtual void handleStopOperation(inet::LifecycleOperation *operation) override { socket.close(); }
    virtual void handleCrashOperation(inet::LifecycleOperation *operation) override { socket.destroy(); }

    virtual void socketDataArrived(inet::UdpSocket *socket, inet::Packet *packet) override;
    virtual void socketErrorArrived(inet::UdpSocket *socket, inet::Indication *indication) override { delete indication; }
    virtual void socketClosed(inet::UdpSocket *socket) override {}
};

} // namespace multiratvanet

#endif
