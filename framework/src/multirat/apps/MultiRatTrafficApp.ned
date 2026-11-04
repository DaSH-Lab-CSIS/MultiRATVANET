//
// MultiRatTrafficApp - one traffic class of a vehicle, sent to a server over
// whichever RAT the MultiRatAppManager has made active.
//
package multiratvanet;

import inet.applications.contract.IApp;

//
// Sends UDP packets to `destAddress`, either at a constant rate (mode "cbr",
// e.g. safety messages) or in on/off bursts (mode "onoff", e.g. infotainment).
// Every packet carries a MultiRatPayload so the receiving MultiRatSink can
// measure delivery, delay, deadlines and the interruption caused by RAT switches.
//
simple MultiRatTrafficApp like IApp
{
    parameters:
        @class(MultiRatTrafficApp);
        @display("i=block/source");
        @lifecycleSupport;
        double stopOperationExtraTime @unit(s) = default(-1s);
        double stopOperationTimeout @unit(s) = default(2s);
        string trafficClass = default("safety");      // label only (results, logs)
        string mode @enum("cbr","onoff") = default("cbr");
        string destAddress = default("server");
        int destPort;
        int localPort = default(-1);
        double startTime @unit(s) = default(3s);         // first packet at max(startTime, appearance) + a random phase within sendInterval
        double stopTime @unit(s) = default(-1s);         // negative: never
        volatile int messageLength @unit(B);
        volatile double sendInterval @unit(s);          // between packets (during an "on" period)
        volatile double onTime @unit(s) = default(1s);  // mode "onoff" only
        volatile double offTime @unit(s) = default(1s); // mode "onoff" only
        string managerModule = default("^.multiRatAppManager");
        @signal[packetSent](type=inet::Packet);
        @statistic[packetSent](title="packets sent"; source=packetSent; record=count,"sum(packetBytes)","vector(packetBytes)"; interpolationmode=none);
    gates:
        input socketIn @labels(UdpControlInfo/up);
        output socketOut @labels(UdpControlInfo/down);
}
