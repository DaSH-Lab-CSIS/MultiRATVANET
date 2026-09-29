//
// V2vBeaconApp - direct V2V safety beaconing over ad-hoc DSRC. See the .h/.cc.
//
package multiratvanet;

import inet.applications.contract.IApp;

//
// Direct vehicle-to-vehicle beaconing application. Periodically broadcasts a
// CAM-like beacon of `beaconBytes` over the dedicated ad-hoc DSRC interface
// (`v2vInterface`, addressed to `groupAddress`), and measures the V2V KPIs from
// the beacons received from neighbouring vehicles.
//
simple V2vBeaconApp like IApp
{
    parameters:
        @class(V2vBeaconApp);
        @display("i=block/app");
        @lifecycleSupport;
        double stopOperationExtraTime @unit(s) = default(-1s);
        double stopOperationTimeout @unit(s) = default(2s);

        string interfaceTableModule;                     // path to the host InterfaceTable
        string v2vInterface = default("wlan2");          // ad-hoc DSRC interface name
        string radioModule = default("^.wlan[2].radio"); // V2V radio, for CBR sensing
        string groupAddress = default("224.0.0.42");     // V2V multicast group
        string v2vAddressBase = default("10.99.0.0");    // base for the V2V interface IP
        string v2vNetmask = default("255.255.0.0");      // netmask of the V2V subnet
        int localPort = default(9001);
        int destPort = default(9001);
        double beaconInterval @unit(s) = default(0.1s);  // 10 Hz CAM rate
        volatile int beaconBytes @unit(B) = default(200B);
        double startTime @unit(s) = default(3s);
        double neighborTimeout @unit(s) = default(1s);   // freshness window for "neighbour"
        double cbrWindow @unit(s) = default(0.1s);       // ETSI-style CBR averaging window

        @signal[v2vBeaconSent](type=inet::Packet);
        @signal[v2vBeaconRcvd](type=inet::Packet);
        @signal[v2vNeighbors](type=long);
        @signal[v2vCbr](type=double);

        @statistic[v2vBeaconSent](title="V2V beacons sent"; source=v2vBeaconSent; record=count,"sum(packetBytes)","vector(packetBytes)"; interpolationmode=none);
        @statistic[v2vBeaconRcvd](title="V2V beacons received"; source=v2vBeaconRcvd; record=count,"sum(packetBytes)","vector(packetBytes)"; interpolationmode=none);
        @statistic[v2vLatency](title="inter-vehicle beacon delay"; source="dataAge(v2vBeaconRcvd)"; unit=s; record=mean,max,vector; interpolationmode=none);
        @statistic[v2vNeighbors](title="neighbouring vehicles in range"; source=v2vNeighbors; record=timeavg,max,vector; interpolationmode=none);
        @statistic[v2vCbr](title="channel busy ratio"; source=v2vCbr; record=mean,max,vector; interpolationmode=sample-hold);
    gates:
        input socketIn @labels(UdpControlInfo/up);
        output socketOut @labels(UdpControlInfo/down);
}
