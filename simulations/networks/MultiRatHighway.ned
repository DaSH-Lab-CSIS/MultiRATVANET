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
        // Network-wide periodic (0.1s) RAT statistics: vehicles-per-RAT + avg RSSI.
        ratStatsCollector: RatStatsCollector {
            @display("p=50,420;is=s");
        }

    connections allowunconnected:
        // Backhaul: every AP/RSU is wired to the core router over Ethernet, so
        // the same server is reachable via cellular (UPF) and via WiFi/DSRC.
        for i=0..numWifiAps-1 {
            wifiAp[i].ethg++ <--> Eth10G <--> router.ethg++;
        }
        for i=0..numDsrcRsus-1 {
            dsrcRsu[i].ethg++ <--> Eth10G <--> router.ethg++;
        }
}
