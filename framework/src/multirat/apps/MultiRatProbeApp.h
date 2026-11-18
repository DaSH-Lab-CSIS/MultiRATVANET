//
// MultiRatProbeApp - a vehicle's probing of its RATs (see MultiRatProbeApp.ned).
//
#ifndef MULTIRATVANET_MULTIRATPROBEAPP_H
#define MULTIRATVANET_MULTIRATPROBEAPP_H

#include <deque>

#include "inet/common/INETDefs.h"
#include "inet/applications/base/ApplicationBase.h"
#include "inet/networklayer/common/L3Address.h"
#include "inet/transportlayer/contract/udp/UdpSocket.h"
#include "base/RatTypes.h"

namespace multiratvanet {

class MultiRatAppManager;
class RatCoverageMonitor;

class MultiRatProbeApp : public inet::ApplicationBase, public inet::UdpSocket::ICallback
{
  protected:
    struct Probe {
        long seq;
        omnetpp::simtime_t sent;
        bool echoed = false;
        double rttMs = 0;
    };
    struct RatProbes {
        std::deque<Probe> recent;       // newest at the back
        double lastRttMs = NAN;
        double lastEchoTime = -1;
        long sent = 0, echoed = 0;
        double rttSumMs = 0;
    };

    int destPort = -1;
    omnetpp::simtime_t probeInterval;
    omnetpp::simtime_t window;       // the mean and the loss cover this long
    omnetpp::simtime_t echoTimeout;  // a probe not echoed after this long counts as lost

    inet::UdpSocket socket;
    inet::L3Address destAddr;
    MultiRatAppManager *manager = nullptr;
    RatCoverageMonitor *monitor = nullptr;
    omnetpp::cMessage *probeTimer = nullptr;
    long seq = 0;
    RatProbes probes[(int)RatId::COUNT];

  protected:
    virtual int numInitStages() const override { return inet::NUM_INIT_STAGES; }
    virtual void initialize(int stage) override;
    virtual void handleMessageWhenUp(omnetpp::cMessage *msg) override;
    virtual void finish() override;

    void probeAll();
    void publish(int rat);

    virtual void handleStartOperation(inet::LifecycleOperation *operation) override;
    virtual void handleStopOperation(inet::LifecycleOperation *operation) override { cancelEvent(probeTimer); socket.close(); }
    virtual void handleCrashOperation(inet::LifecycleOperation *operation) override { cancelEvent(probeTimer); socket.destroy(); }

    virtual void socketDataArrived(inet::UdpSocket *socket, inet::Packet *packet) override;
    virtual void socketErrorArrived(inet::UdpSocket *socket, inet::Indication *indication) override { delete indication; }
    virtual void socketClosed(inet::UdpSocket *socket) override {}

  public:
    virtual ~MultiRatProbeApp();
};

} // namespace multiratvanet

#endif
