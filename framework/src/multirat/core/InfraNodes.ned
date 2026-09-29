//
// Infrastructure access nodes for the WiFi and DSRC RATs.
//
// Both are thin wrappers around INET's AccessPoint so that (a) the
// RatCoverageMonitor can discover them by distinct NED type names ("WifiAp"
// vs "DsrcRsu"), and (b) each RAT gets its own PHY defaults and radio medium.
// DSRC is approximated as an 802.11 infrastructure link at 5.9 GHz.
//
package multiratvanet;

import inet.node.wireless.AccessPoint;

module WifiAp extends AccessPoint
{
    parameters:
        @display("i=device/accesspoint;bgb=,,#d0e0ff");
        wlan[*].radio.centerFrequency = default(2.412GHz);
        wlan[*].radio.bandwidth = default(20MHz);
        wlan[*].radio.transmitter.power = default(0.1W);
}

module DsrcRsu extends AccessPoint
{
    parameters:
        @display("i=device/antennatower;bgb=,,#ffe0d0");
        // DSRC approximated as an infrastructure 802.11 link at 5.9 GHz / 10 MHz.
        wlan[*].radio.centerFrequency = default(5.9GHz);
        wlan[*].radio.bandwidth = default(10MHz);
        wlan[*].radio.transmitter.power = default(0.2W);
}
