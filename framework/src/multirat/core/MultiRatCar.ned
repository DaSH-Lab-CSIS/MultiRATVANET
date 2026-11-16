//
// MultiRatCar: a vehicular node that carries multiple radio access
// technologies simultaneously and switches the active one at the application
// layer based on coverage and QoS.
//
// It extends the Simu5G NrCar (which already provides the LTE/5G-NR cellularNic,
// VeinsInetMobility, an IPv4 network layer and layer message-dispatchers) and
// adds INET Ieee80211 interfaces for WiFi and a DSRC (802.11p @5.9 GHz)
// approximation, wired into the same 'nl' network<->link dispatcher so that all
// RATs share one IPv4 stack (unified-IP handover).
//
package multiratvanet;

import inet.linklayer.contract.IWirelessInterface;
import simu5g.nodes.NrCar;

module MultiRatCar extends NrCar
{
    parameters:
        @display("i=device/car");

        // wlan[0] = DSRC (802.11p / 5.9 GHz), wlan[1] = WiFi (802.11 a/g/n)
        int numWlanInterfaces = default(2);

        // auto-assign IPv4 to the WiFi/DSRC interfaces; the cellular interface
        // IP is provisioned by the Simu5G stack (Binder), not the configurator.
        ipv4.configurator.interfaces = default("wlan*");

        // the control plane of the framework lives in these two submodules
        *.coverageMonitorModule = default(absPath(".ratCoverageMonitor"));
        *.appManagerModule = default(absPath(".multiRatAppManager"));

    gates:
        // radio path-start gates for the wlan interfaces; the RadioMedium sends
        // signals to getPathStartGate() of each radio's radioIn.
        input wlanRadioIn[numWlanInterfaces] @directIn;

    submodules:
        wlan[numWlanInterfaces]: <default("Ieee80211Interface")> like IWirelessInterface {
            @display("p=650,523,row,150;q=queue");
        }
        ratCoverageMonitor: RatCoverageMonitor {
            @display("p=126.4,470,r,10;i=block/cogwheel");
        }
        multiRatAppManager: MultiRatAppManager {
            @display("p=750,72;i=block/app");
        }

    connections allowunconnected:
        for i=0..numWlanInterfaces-1 {
            wlanRadioIn[i] --> wlan[i].radioIn;
            wlan[i].upperLayerOut --> nl.in++;
            wlan[i].upperLayerIn <-- nl.out++;
        }
}
