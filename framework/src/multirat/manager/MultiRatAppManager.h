//
// MultiRatAppManager.h
//
#ifndef MULTIRATVANET_MULTIRATAPPMANAGER_H
#define MULTIRATVANET_MULTIRATAPPMANAGER_H

#include <omnetpp.h>
#include <fstream>
#include <map>
#include <memory>
#include <string>
#include "base/PolicyTypes.h"
#include "base/RatTypes.h"
#include "policies/IRatSelectionPolicy.h"

#include "inet/networklayer/contract/ipv4/Ipv4Address.h"

namespace inet { class IInterfaceTable; class IIpv4RoutingTable; class IMobility; }

namespace multiratvanet {

class RatCoverageMonitor;

//
// Application-layer controller that selects and switches the active RAT and
// records handover performance metrics.
//
class MultiRatAppManager : public omnetpp::cSimpleModule
{
  public:
    RatId getActiveRat() const { return current_; }
    long getSwitchCount() const { return handoverTotal_; }  // completed switches so far
    virtual ~MultiRatAppManager();

    // --- for the vehicle's traffic and probe apps ---
    // A traffic class announces itself; from then on the policy is told about it and can
    // choose a RAT for it.
    void registerTrafficClass(const std::string &trafficClass);
    // The RAT the class is sent on now (the policy's choice for it, else the default RAT), and
    // how many times that has changed.
    RatId getClassRat(const std::string &trafficClass) const;
    long getClassSwitchCount(const std::string &trafficClass) const;
    // How to send over one particular RAT whatever the default route is: its interface and
    // gateway (unspecified = on-link). False if the RAT has no usable interface.
    bool getRatRoute(RatId rat, int &interfaceId, inet::Ipv4Address &gateway) const;
    // What the vehicle sees of its own traffic: requests it sent and replies that came back.
    void reportRequest(const std::string &trafficClass, int repliesExpected);
    void reportReply(const std::string &trafficClass, double delay);


  protected:
    virtual int numInitStages() const override;
    virtual void initialize(int stage) override;
    virtual void handleMessage(omnetpp::cMessage *msg) override;
    virtual void finish() override;

  private:
    void decide();
    void logDecision(RatId before, const PolicyResponse &response, const RatMetricsVec &metrics);
    std::shared_ptr<std::ofstream> decisionLog_;  // CSV shared by all cars of the run (decisionLog parameter)
    PolicyRequest buildRequest();         // what the vehicle knows now
    void attach(RatId target);            // initial RAT selection (no handover cost)
    void initiateHandover(RatId target);  // start a make-before-break switch
    void applyHandover();                 // complete the pending switch
    bool applyDefaultRoute(RatId target); // rewrite the IPv4 default route
    void configureWlanInterfaces();       // assign IPv4 to the DSRC/WiFi NICs
    void accountResidency();
    inet::Ipv4Address gatewayOf(int ratIdx) const;
    void applyDefaultRat(RatId target, const RatMetricsVec &metrics);
    void updateClassRats();               // classes follow the default RAT unless the policy named another

    // config / references
    std::unique_ptr<IRatSelectionPolicy> policy_;
    RatCoverageMonitor *monitor_ = nullptr;
    inet::IInterfaceTable *ift_ = nullptr;
    inet::IIpv4RoutingTable *rt_ = nullptr;
    inet::IMobility *mobility_ = nullptr;

    // what the policy is told besides the per-RAT measurements
    int vehicleId_ = -1;
    std::string externalId_;
    long requestSeq_ = 0;
    PreviousDecision previous_;

    // one per traffic class of the vehicle
    struct ClassState {
        RatId rat = RatId::NONE;          // RAT the class is sent on
        RatId overrideRat = RatId::NONE;  // the policy's own choice for the class; NONE = the default RAT
        long switches = 0;
        double since = 0.0;
        double residency[(int)RatId::COUNT] = {0};
        TrafficCounters window, total;
    };
    std::map<std::string, ClassState> classes_;

    std::string ifaceName_[(int)RatId::COUNT];
    std::string gateway_[(int)RatId::COUNT];

    double decisionInterval_ = 0.5;
    double handoverExecDelay_ = 0.05;
    double handoverDelayPerRat_[(int)RatId::COUNT] = {0};
    double pingPongWindow_ = 2.0;

    // state
    RatId current_ = RatId::NONE;
    RatId pendingTarget_ = RatId::NONE;
    RatId lastRat_ = RatId::NONE;       // RAT active before current_ (ping-pong)
    bool inHandover_ = false;
    double currentSince_ = 0.0;
    double lastSwitchTime_ = 0.0;
    double residency_[(int)RatId::COUNT] = {0};
    long handoverTotal_ = 0;
    long pingPongTotal_ = 0;

    // measured handover delay (initiation -> route installed)
    double handoverStartTime_ = 0.0;   // sim time the pending switch began
    double handoverDelaySum_ = 0.0;    // s, accumulated measured delay
    double handoverDelayMax_ = 0.0;    // s, worst measured delay

    // timers
    omnetpp::cMessage *decisionTimer_ = nullptr;
    omnetpp::cMessage *applyTimer_ = nullptr;

    // signals
    omnetpp::simsignal_t handoverCountSignal_ = -1;
    omnetpp::simsignal_t handoverLatencySignal_ = -1;
    omnetpp::simsignal_t handoverPairSignal_ = -1;
    omnetpp::simsignal_t pingPongSignal_ = -1;
    omnetpp::simsignal_t activeRatSignal_ = -1;
    omnetpp::simsignal_t outageTimeSignal_ = -1;
    omnetpp::simsignal_t decisionCountSignal_ = -1;
    omnetpp::simsignal_t handoverFailedSignal_ = -1;
    omnetpp::simsignal_t decisionRejectedSignal_ = -1;
};

} // namespace multiratvanet

#endif
