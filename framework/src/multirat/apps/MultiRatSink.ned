//
// MultiRatSink - server side of one MultiRatTrafficApp traffic class (or of the probes).
//
package multiratvanet;

import inet.applications.contract.IApp;

//
// Receives the requests of one traffic class and answers each as the request asks: the number
// of reply packets, their size and their spacing are in the request, and they go back to the
// address the request came from, so over the RAT it was sent on. It measures:
//   - delivery and end-to-end delay of the requests (same statistics as INET's UdpSink);
//   - deadline: requests that arrived within `deadline` of being sent;
//   - requests received per RAT they were sent on;
//   - switch interruption: for every RAT switch of a sender, the time from its
//     first request sent after the switch until the first of those that
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
        @signal[replySent](type=inet::Packet);
        @signal[switchInterruption](type=double);
        @signal[switchLoss](type=long);
        @statistic[packetReceived](title="requests received"; source=packetReceived; record=count,"sum(packetBytes)","vector(packetBytes)"; interpolationmode=none);
        @statistic[replySent](title="reply packets sent"; source=replySent; record=count,"sum(packetBytes)","vector(packetBytes)"; interpolationmode=none);
        @statistic[throughput](title="throughput"; unit=bps; source="throughput(packetReceived)"; record=vector);
        @statistic[endToEndDelay](title="end-to-end delay of requests"; source="dataAge(packetReceived)"; unit=s; record=histogram,vector; interpolationmode=none);
        @statistic[switchInterruption](title="time until the new RAT delivers"; unit=s; record=histogram,vector; interpolationmode=none);
        @statistic[switchLoss](title="requests lost right after a switch"; record=sum,histogram; interpolationmode=none);
    gates:
        input socketIn @labels(UdpControlInfo/up);
        output socketOut @labels(UdpControlInfo/down);
}
