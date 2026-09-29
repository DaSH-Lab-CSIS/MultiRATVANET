//
// V2vBeaconApp - direct vehicle-to-vehicle (V2V) safety-beaconing application.
//
// Each vehicle periodically broadcasts a CAM-like beacon over its dedicated
// ad-hoc DSRC (802.11p / OCB) interface, and listens for the beacons of
// neighbouring vehicles on the same link. Because the beacons travel over an
// ad-hoc interface they are delivered directly car-to-car, with no RSU / AP in
// the path (true single-hop V2V).
//
// The application derives the classic V2V KPIs:
//   * neighbour count        - distinct vehicles heard within a freshness window;
//   * beacon reception ratio - per-sender received/expected (from sequence gaps);
//   * inter-vehicle latency  - one-way beacon delay (dataAge of received beacons);
//   * beacon load            - beacons / bytes sent and received.
//
// Beacons are addressed to an IPv4 multicast group pinned to the V2V interface,
// so at the 802.11 MAC they are transmitted as broadcast and every in-range
// ad-hoc peer receives them.
//

#ifndef MULTIRATVANET_V2VBEACONAPP_H
#define MULTIRATVANET_V2VBEACONAPP_H

#include <map>

#include "inet/common/INETDefs.h"
#include "inet/applications/base/ApplicationBase.h"
#include "inet/networklayer/common/L3Address.h"
#include "inet/transportlayer/contract/udp/UdpSocket.h"

namespace multiratvanet {

class V2vBeaconApp : public inet::ApplicationBase, public inet::UdpSocket::ICallback, public omnetpp::cListener
{
  protected:
    // per-neighbour reception bookkeeping (keyed by sender L3 address)
    struct SenderRec {
        long firstSeq = -1;
        long lastSeq = -1;
        long count = 0;
        double lastSeen = 0.0;
    };

    // parameters
    int localPort = -1;
    int destPort = -1;
    const char *groupAddressStr = nullptr;
    const char *v2vInterfaceName = nullptr;
    omnetpp::simtime_t beaconInterval;
    omnetpp::simtime_t startTime;
    double neighborTimeout = 0.0;
    double cbrWindow = 0.1;

    // state
    inet::UdpSocket socket;
    inet::L3Address groupAddr;
    int v2vInterfaceId = -1;
    omnetpp::cMessage *beaconTimer = nullptr;
    long seqNo = 0;
    long beaconsSent = 0;
    long beaconsReceived = 0;

    std::map<inet::L3Address, SenderRec> senders;

    // time-weighted neighbour accounting
    double lastSampleTime = 0.0;
    double neighborIntegral = 0.0;
    double sampledTime = 0.0;
    long maxNeighbors = 0;

    // channel-busy-ratio (CBR) accounting on the V2V radio
    omnetpp::cModule *radioModule_ = nullptr;
    omnetpp::cMessage *cbrTimer = nullptr;
    bool rxBusy = false;
    bool txBusy = false;
    bool channelBusy = false;
    omnetpp::simtime_t lastBusyChange;
    omnetpp::simtime_t busyAccum;         // busy time in the current CBR window
    omnetpp::simtime_t totalBusyTime;     // cumulative busy time over the run
    omnetpp::simtime_t cbrObsStart;       // start of CBR observation
    double maxCbr = 0.0;                  // peak per-window CBR

    // signals
    omnetpp::simsignal_t beaconSentSignal_;
    omnetpp::simsignal_t beaconRcvdSignal_;
    omnetpp::simsignal_t neighborsSignal_;
    omnetpp::simsignal_t cbrSignal_;

  protected:
    virtual int numInitStages() const override { return inet::NUM_INIT_STAGES; }
    virtual void initialize(int stage) override;
    virtual void handleMessageWhenUp(omnetpp::cMessage *msg) override;
    virtual void finish() override;

    // lifecycle
    virtual void handleStartOperation(inet::LifecycleOperation *operation) override;
    virtual void handleStopOperation(inet::LifecycleOperation *operation) override;
    virtual void handleCrashOperation(inet::LifecycleOperation *operation) override;

    // UdpSocket::ICallback
    virtual void socketDataArrived(inet::UdpSocket *socket, inet::Packet *packet) override;
    virtual void socketErrorArrived(inet::UdpSocket *socket, inet::Indication *indication) override;
    virtual void socketClosed(inet::UdpSocket *socket) override;

    // listen to the V2V radio's medium-state signals for CBR
    virtual void receiveSignal(omnetpp::cComponent *source, omnetpp::simsignal_t signalID,
            long value, omnetpp::cObject *details) override;

    void sendBeacon();
    void processBeacon(inet::Packet *packet);
    long sampleNeighbors();
    void accountBusyUpTo(omnetpp::simtime_t now);

  public:
    V2vBeaconApp() {}
    virtual ~V2vBeaconApp();
};

} // namespace multiratvanet

#endif // MULTIRATVANET_V2VBEACONAPP_H
