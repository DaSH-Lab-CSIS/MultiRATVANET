//
// MultiRatTrafficApp - one traffic class of a vehicle, exchanged with a server over
// whichever RAT the policy has chosen for the class.
//
package multiratvanet;

import inet.applications.contract.IApp;

//
// Traffic is request-and-reply. The app sends UDP requests to `destAddress`, either at a
// constant rate (mode "cbr") or in on/off bursts (mode "onoff"), and each request asks the
// server (a MultiRatSink) for `replyCount` reply packets of `replyLength`, `replyInterval` apart.
// The server sends them to the address the request came from, so over the same RAT.
//   safety:       a 200 B message every 100 ms, answered by one small acknowledgement
//   infotainment: a small request every 100 ms during a burst, answered by ten 1250 B data
//                 packets (the heavy direction is server -> vehicle)
// The replies are all the vehicle sees of how the class is doing; the app passes their count and
// delay to the MultiRatAppManager, which gives them to the policy. Requests are scored at the
// server (MultiRatSink), replies here: `deadline` is counted from the sending of the request.
//
simple MultiRatTrafficApp like IApp
{
    parameters:
        @class(MultiRatTrafficApp);
        @display("i=block/source");
        @lifecycleSupport;
        double stopOperationExtraTime @unit(s) = default(-1s);
        double stopOperationTimeout @unit(s) = default(2s);
        string trafficClass = default("safety");      // name of the class: the policy chooses a RAT per class
        string mode @enum("cbr","onoff") = default("cbr");
        string destAddress = default("server");
        int destPort;
        int localPort = default(-1);
        double startTime @unit(s) = default(3s);         // first request at max(startTime, appearance) + a random phase within sendInterval
        double stopTime @unit(s) = default(-1s);         // negative: never
        volatile int messageLength @unit(B);            // size of a request
        volatile double sendInterval @unit(s);          // between requests (during an "on" period)
        volatile double onTime @unit(s) = default(1s);  // mode "onoff" only
        volatile double offTime @unit(s) = default(1s); // mode "onoff" only
        int replyCount = default(0);                    // reply packets asked for per request (0: none)
        volatile int replyLength @unit(B) = default(50B); // size of each
        double replyInterval @unit(s) = default(0s);    // spacing between them
        double deadline @unit(s) = default(0s);         // a reply is in time if it arrives this long after its request was sent; 0: no deadline
        string managerModule = default("^.multiRatAppManager"); // the car's MultiRatAppManager; "" = none
        @signal[packetSent](type=inet::Packet);
        @signal[replyReceived](type=inet::Packet);
        @signal[replyDelay](type=double);
        @statistic[packetSent](title="requests sent"; source=packetSent; record=count,"sum(packetBytes)","vector(packetBytes)"; interpolationmode=none);
        @statistic[replyReceived](title="reply packets received"; source=replyReceived; record=count,"sum(packetBytes)","vector(packetBytes)"; interpolationmode=none);
        @statistic[replyDelay](title="request sent to reply received"; unit=s; record=histogram,vector; interpolationmode=none);
    gates:
        input socketIn @labels(UdpControlInfo/up);
        output socketOut @labels(UdpControlInfo/down);
}
