//
// MultiRatAppManager - application-layer RAT switching stack + handover KPIs.
//
// Every decisionInterval it builds a PolicyRequest for this vehicle (who and where
// it is, what it is connected through, the per-RAT measurements from the
// RatCoverageMonitor and what became of the previous decision) and asks the
// configured policy which RAT to use. The manager adds nothing of its own to the
// decision: no waiting, no smoothing. If the answer differs
// from the current RAT and is in range, it executes a handover by swapping the
// IPv4 default route onto that RAT's interface. docs/POLICY_REFERENCE.md describes
// the request, the response and how to write a policy.
//
// A RAT is only usable while the RatCoverageMonitor reports it in range
// (measured, above threshold, 802.11 associated), so the route moves
// immediately; what the switch really costs (queued packets on the old link,
// the new link's first-packet delay) comes out of the simulated stacks and is
// measured at the receiver by MultiRatSink. Handover counts and ping-pong are
// emitted as signals.
//
package multiratvanet;

simple MultiRatAppManager
{
    parameters:
        @class(MultiRatAppManager);
        @display("i=block/app");

        string coverageMonitorModule;   // path to the RatCoverageMonitor
        string routingTableModule = default("^.ipv4.routingTable");
        string interfaceTableModule = default("^.interfaceTable");

        string policy = default("CoveragePriority"); // CoveragePriority|Sinr|LatencyQos|Load|Ml|Ensemble|ExampleSplit
        double decisionInterval @unit(s) = default(0.5s);
        // Scenario setting, not a policy tool: extra delay before the route moves, for signalling
        // the stacks do not simulate (e.g. IP mobility). 0 = the switch costs only what the
        // simulated stacks cost.
        double handoverExecDelay @unit(s) = default(0s);
        double pingPongWindow @unit(s) = default(2s);
        double startTime @unit(s) = default(1s);   // after the car appears; plus a random phase within decisionInterval

        // ---- Policy tunables ----
        // A different usable RAT must stay the policy's choice for this long before the switch
        // (all policies; Ensemble applies it to the outcome of the vote). Losing the current RAT
        // switches at once.
        double timeToTrigger @unit(s) = default(1s);
        double sinrSwitchMargin @unit(dB) = default(3dB); // Sinr: SINR-margin gain needed to prefer another RAT
        double loadSwitchMargin = default(0.15);          // Load: load reduction (0..1) needed to prefer another RAT
        double latencyBudget @unit(s) = default(100ms);   // LatencyQos: estimated latency a RAT must stay within

        // Per-target-RAT version of handoverExecDelay (each defaults to it).
        double dsrcHandoverDelay @unit(s) = default(handoverExecDelay);
        double wifiHandoverDelay @unit(s) = default(handoverExecDelay);
        double lteHandoverDelay  @unit(s) = default(handoverExecDelay);
        double nrHandoverDelay   @unit(s) = default(handoverExecDelay);
        double sixgHandoverDelay @unit(s) = default(handoverExecDelay);

        // ---- Ensemble ("Ensemble" policy) per-voter weights (0 disables a voter) ----
        double ensembleWeightCoverage = default(1.0);
        double ensembleWeightSinr     = default(1.0);
        double ensembleWeightLatency  = default(1.0);
        double ensembleWeightLoad     = default(1.0);
        double ensembleStickiness     = default(1.0); // keep current if within this vote margin of the leader

        // Interface names per RAT (as registered in the InterfaceTable).
        string dsrcInterface = default("wlan0");
        string wifiInterface = default("wlan1");
        string lteInterface  = default("cellular");
        string nrInterface   = default("cellular");
        string sixgInterface = default("sixg0");

        // Gateway per RAT: an IPv4 address, or "<module>%<interface>" (e.g. "router%eth0") for
        // the address of that interface; "" => on-link / unspecified.
        string dsrcGateway = default("");
        string wifiGateway = default("");
        string lteGateway  = default("");
        string nrGateway   = default("");
        string sixgGateway = default("");

        // ---- Handover performance metrics ----
        @signal[handoverCount](type=long);   // 1 per completed handover
        @signal[handoverLatency](type=double); // s, decision to route change (= the extra delay above)
        @signal[handoverPair](type=long);     // fromRat*10 + toRat
        @signal[pingPong](type=long);         // 1 per detected ping-pong
        @signal[activeRat](type=long);        // current RAT index over time
        @signal[outageTime](type=double);     // s, same as handoverLatency; real interruption: MultiRatSink
        @signal[decisionCount](type=long);    // 1 per policy evaluation
        @signal[handoverFailed](type=long);   // 1 per aborted handover (target lost)
        @signal[decisionRejected](type=long); // 1 per policy answer naming a RAT that was not in range

        @statistic[handoverCount](title="handovers"; record=count,last,vector);
        @statistic[handoverLatency](title="handover latency"; unit=s; record=mean,max,vector);
        @statistic[handoverPair](title="handover from*10+to"; record=vector);
        @statistic[pingPong](title="ping-pong handovers"; record=count,last);
        @statistic[activeRat](title="active RAT index"; record=vector);
        @statistic[outageTime](title="handover outage"; unit=s; record=sum,mean,vector);
        @statistic[decisionCount](title="policy decisions"; record=count,last);
        @statistic[handoverFailed](title="failed handovers"; record=count,last);
        @statistic[decisionRejected](title="policy answers rejected (RAT not in range)"; record=count,last);
}
