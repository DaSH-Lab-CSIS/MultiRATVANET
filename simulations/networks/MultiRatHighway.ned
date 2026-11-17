//
// MultiRatHighway - multi-RAT VANET scenario.
//
// Extends the Simu5G NR "cars" Highway (which already provides the LTE/5G-NR
// core: gNodeBs, UPF, router, server, Binder, channel control and the Veins
// manager) and adds the WiFi and DSRC access infrastructure plus their radio
// media. Cars are instantiated by the veinsManager as multiratvanet.MultiRatCar
// (set in omnetpp.ini).
//
package multiratvanet.simulations;

import simu5g.simulations.nr.cars.Highway;
import inet.physicallayer.wireless.ieee80211.packetlevel.Ieee80211ScalarRadioMedium;
import inet.node.ethernet.Eth10G;
import inet.node.ethernet.EthernetSwitch;
import multiratvanet.WifiAp;
import multiratvanet.DsrcRsu;
import multiratvanet.RatStatsCollector;

network MultiRatHighway extends Highway
{
    parameters:
        int numWifiAps = default(2);
        int numDsrcRsus = default(3);
        @display("bgb=900,500");

    submodules:
        // Separate media isolate the 2.4 GHz WiFi channel from the 5.9 GHz DSRC one.
        wifiMedium: Ieee80211ScalarRadioMedium {
            @display("p=50,300;is=s");
        }
        dsrcMedium: Ieee80211ScalarRadioMedium {
            @display("p=50,350;is=s");
        }
        wifiAp[numWifiAps]: WifiAp {
            @display("p=250,60;is=n");
        }
        dsrcRsu[numDsrcRsus]: DsrcRsu {
            @display("p=250,420;is=n");
        }
        // Distribution networks: one LAN per RAT, each behind its own router port.
        dsrcSwitch: EthernetSwitch {
            @display("p=150,300;is=s");
        }
        wifiSwitch: EthernetSwitch {
            @display("p=150,180;is=s");
        }
        // Network-wide periodic (0.1s) RAT statistics: vehicles-per-RAT + avg RSSI.
        ratStatsCollector: RatStatsCollector {
            @display("p=50,420;is=s");
        }

    connections allowunconnected:
        // Backhaul: the RSUs sit on one switched LAN and the APs on another, each with its own
        // uplink to the core router, so the server is reachable via cellular (UPF), via DSRC and
        // via WiFi, and its replies come back the same way. One LAN per RAT means one gateway per
        // RAT: a car that moves between RSUs (or between APs) keeps a valid ARP entry, and the
        // router's ARP for a car's DSRC address is heard on DSRC only. (On a single shared LAN a
        // car answered it from whichever of its two radios heard it, and replies came back on the
        // wrong RAT.) The order matters: DSRC is the router's eth0, WiFi its eth1 (router.mrt, omnetpp.ini).
        dsrcSwitch.ethg++ <--> Eth10G <--> router.ethg++;
        wifiSwitch.ethg++ <--> Eth10G <--> router.ethg++;
        for i=0..numWifiAps-1 {
            wifiAp[i].ethg++ <--> Eth10G <--> wifiSwitch.ethg++;
        }
        for i=0..numDsrcRsus-1 {
            dsrcRsu[i].ethg++ <--> Eth10G <--> dsrcSwitch.ethg++;
        }
}
