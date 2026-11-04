//
// MultiRatSink - server side of one MultiRatTrafficApp traffic class.
//
package multiratvanet;

import inet.applications.contract.IApp;

//
// Receives one traffic class and measures:
//   - delivery and end-to-end delay (same statistics as INET's UdpSink);
//   - deadline: packets that arrived within `deadline` of being sent;
//   - packets received per RAT they were sent on;
//   - switch interruption: for every RAT switch of a sender, the time from its
//     first packet sent after the switch until the first of those packets that
//     arrives, and how many were lost before that one.
//
simple MultiRatSink like IApp
{
    parameters:
        @class(MultiRatSink);
        @display("i=block/sink");
        @lifecycleSupport;
        double stopOperationExtraTime @unit(s) = default(-1s);
        double stopOperationTimeout @unit(s) = default(2s);
        string trafficClass = default("safety");
        int localPort;
        double deadline @unit(s) = default(0s);   // 0: no deadline
        @signal[packetReceived](type=inet::Packet);
        @signal[switchInterruption](type=double);
        @signal[switchLoss](type=long);
        @statistic[packetReceived](title="packets received"; source=packetReceived; record=count,"sum(packetBytes)","vector(packetBytes)"; interpolationmode=none);
        @statistic[throughput](title="throughput"; unit=bps; source="throughput(packetReceived)"; record=vector);
        @statistic[endToEndDelay](title="end-to-end delay"; source="dataAge(packetReceived)"; unit=s; record=histogram,vector; interpolationmode=none);
        @statistic[switchInterruption](title="time until the new RAT delivers"; unit=s; record=histogram,vector; interpolationmode=none);
        @statistic[switchLoss](title="packets lost right after a switch"; record=sum,histogram; interpolationmode=none);
    gates:
        input socketIn @labels(UdpControlInfo/up);
        output socketOut @labels(UdpControlInfo/down);
}
