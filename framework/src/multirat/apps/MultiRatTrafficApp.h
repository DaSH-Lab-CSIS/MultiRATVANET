//
// MultiRatTrafficApp - one traffic class of a vehicle (see MultiRatTrafficApp.ned).
//
#ifndef MULTIRATVANET_MULTIRATTRAFFICAPP_H
#define MULTIRATVANET_MULTIRATTRAFFICAPP_H

#include "inet/common/INETDefs.h"
#include "inet/applications/base/ApplicationBase.h"
#include "inet/networklayer/common/L3Address.h"
#include "inet/transportlayer/contract/udp/UdpSocket.h"
#include "base/RatTypes.h"

namespace multiratvanet {

class MultiRatAppManager;

class MultiRatTrafficApp : public inet::ApplicationBase, public inet::UdpSocket::ICallback
{
  protected:
    // parameters
    bool onOff = false;
    int destPort = -1;
    omnetpp::simtime_t startTime;
    omnetpp::simtime_t stopTime;

    // state
    inet::UdpSocket socket;
    inet::L3Address destAddr;
    MultiRatAppManager *manager = nullptr;
    omnetpp::cMessage *sendTimer = nullptr;
    omnetpp::simtime_t burstEnd;          // end of the current "on" period (mode onoff)
    long seq = 0;
    long epochSwitchCount = -1;           // manager switch count when the current epoch began
    long epochStartSeq = 0;
    omnetpp::simtime_t epochStartTime;
    long sentPerRat[(int)RatId::COUNT] = {0};
    long sentNoRat = 0;

    omnetpp::simsignal_t packetSentSignal = -1;

  protected:
    virtual int numInitStages() const override { return inet::NUM_INIT_STAGES; }
    virtual void initialize(int stage) override;
    virtual void handleMessageWhenUp(omnetpp::cMessage *msg) override;
    virtual void finish() override;

    void sendPacket();
    void scheduleNext();

    virtual void handleStartOperation(inet::LifecycleOperation *operation) override;
    virtual void handleStopOperation(inet::LifecycleOperation *operation) override;
    virtual void handleCrashOperation(inet::LifecycleOperation *operation) override;

    virtual void socketDataArrived(inet::UdpSocket *socket, inet::Packet *packet) override { delete packet; }
    virtual void socketErrorArrived(inet::UdpSocket *socket, inet::Indication *indication) override { delete indication; }
    virtual void socketClosed(inet::UdpSocket *socket) override {}

  public:
    virtual ~MultiRatTrafficApp();
};

} // namespace multiratvanet

#endif
