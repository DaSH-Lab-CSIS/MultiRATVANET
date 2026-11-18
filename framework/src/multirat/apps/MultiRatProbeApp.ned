//
// MultiRatProbeApp - a vehicle's probing of its RATs.
//
package multiratvanet;

import inet.applications.contract.IApp;

//
// A car cannot know how a RAT it is not using would perform unless it tries it. Every
// `probeInterval` this app sends one small packet over every RAT whose link is up, each out of
// that RAT's own interface; the server (a MultiRatSink) echoes it to the address it came from.
// From the echoes the car knows, per RAT, the round-trip time and the share of probes lost. The
// app hands these to the RatCoverageMonitor, which gives them to the policy and can require a
// recent echo before it calls a RAT usable.
//
// Probing is part of the harness, the same for every policy: a policy cannot change or stop it.
// It is real traffic and loads the channels like any other.
//
simple MultiRatProbeApp like IApp
{
    parameters:
        @class(MultiRatProbeApp);
        @display("i=block/timer");
        @lifecycleSupport;
        double stopOperationExtraTime @unit(s) = default(-1s);
        double stopOperationTimeout @unit(s) = default(2s);
        string destAddress = default("server");
        int destPort;
        int localPort = default(-1);
        double startTime @unit(s) = default(0s);          // after the car appears; plus a random phase within probeInterval
        double probeInterval @unit(s) = default(0.1s);    // one probe per linked RAT this often
        int probeLength @unit(B) = default(50B);          // size of a probe and of its echo
        double window @unit(s) = default(1s);             // the mean round trip and the loss cover this long
        double echoTimeout @unit(s) = default(0.5s);      // a probe not echoed after this long counts as lost
        string managerModule = default("^.multiRatAppManager");
        string coverageMonitorModule = default("^.ratCoverageMonitor");
    gates:
        input socketIn @labels(UdpControlInfo/up);
        output socketOut @labels(UdpControlInfo/down);
}
