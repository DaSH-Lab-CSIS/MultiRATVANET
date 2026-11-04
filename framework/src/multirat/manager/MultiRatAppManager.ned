//
// MultiRatAppManager - application-layer RAT switching stack + handover KPIs.
//
// Periodically (or on a coverage change) it reads the per-RAT metrics from the
// RatCoverageMonitor, asks the configured IRatSelectionPolicy which RAT should
// be active, and - if that differs from the current RAT and is in range -
// executes a handover by swapping the IPv4 default route onto the selected
// RAT's interface. A RAT is only offered to the policy while it is usable
// (RatCoverageMonitor: measured, above threshold, 802.11 associated), so the
// route moves immediately; what the switch really costs (queued packets on the
// old link, the new link's first-packet delay) comes out of the simulated
// stacks and is measured at the receiver by MultiRatSink. Handover counts and
// ping-pong are emitted as signals.
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

        string policy = default("CoveragePriority"); // CoveragePriority|Sinr|LatencyQos|Load|Ml|Ensemble
        double decisionInterval @unit(s) = default(0.5s);
        bool decideOnlyOnCoverageChange = default(false);
        // Extra delay before the route moves, for signalling the stacks do not simulate
        // (e.g. IP mobility). 0 = the switch costs only what the simulated stacks cost.
        double handoverExecDelay @unit(s) = default(0s);
        double pingPongWindow @unit(s) = default(2s);
        double startTime @unit(s) = default(1s);   // after the car appears; plus a random phase within decisionInterval

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

        // Optional default-route gateway per RAT ("" => on-link / unspecified).
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

        @statistic[handoverCount](title="handovers"; record=count,last,vector);
        @statistic[handoverLatency](title="handover latency"; unit=s; record=mean,max,vector);
        @statistic[handoverPair](title="handover from*10+to"; record=vector);
        @statistic[pingPong](title="ping-pong handovers"; record=count,last);
        @statistic[activeRat](title="active RAT index"; record=vector);
        @statistic[outageTime](title="handover outage"; unit=s; record=sum,mean,vector);
        @statistic[decisionCount](title="policy decisions"; record=count,last);
        @statistic[handoverFailed](title="failed handovers"; record=count,last);
}
