//
// MultiRatAppManager.h
//
#ifndef MULTIRATVANET_MULTIRATAPPMANAGER_H
#define MULTIRATVANET_MULTIRATAPPMANAGER_H

#include <omnetpp.h>
#include <memory>
#include <string>
#include "RatTypes.h"
#include "policies/IRatSelectionPolicy.h"

namespace inet { class IInterfaceTable; class IIpv4RoutingTable; }

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

  protected:
    virtual int numInitStages() const override;
    virtual void initialize(int stage) override;
    virtual void handleMessage(omnetpp::cMessage *msg) override;
    virtual void finish() override;

  private:
    void decide();
    void attach(RatId target);            // initial RAT selection (no handover cost)
    void initiateHandover(RatId target);  // start a make-before-break switch
    void applyHandover();                 // complete the pending switch
    bool applyDefaultRoute(RatId target); // rewrite the IPv4 default route
    void configureWlanInterfaces();       // assign IPv4 to the DSRC/WiFi NICs
    void accountResidency();

    // config / references
    std::unique_ptr<IRatSelectionPolicy> policy_;
    RatCoverageMonitor *monitor_ = nullptr;
    inet::IInterfaceTable *ift_ = nullptr;
    inet::IIpv4RoutingTable *rt_ = nullptr;

    std::string ifaceName_[(int)RatId::COUNT];
    std::string gateway_[(int)RatId::COUNT];

    double decisionInterval_ = 0.5;
    double handoverExecDelay_ = 0.05;
    double handoverDelayPerRat_[(int)RatId::COUNT] = {0};
    double pingPongWindow_ = 2.0;
    bool decideOnlyOnCoverageChange_ = false;

    // state
    RatId current_ = RatId::NONE;
    RatId pendingTarget_ = RatId::NONE;
    RatId lastRat_ = RatId::NONE;       // RAT active before current_ (ping-pong)
    bool inHandover_ = false;
    double currentSince_ = 0.0;
    double lastSwitchTime_ = 0.0;
    unsigned long lastCoverageMask_ = 0;
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
};

} // namespace multiratvanet

#endif
