//
// ElectronicCity - Bangalore OSM-based long-run scenario.
//
// Reuses the known-good MultiRatHighway baseline wiring (Veins manager, Simu5G
// core, WiFi/DSRC media) and scales the infrastructure to 15 APs/15 RSUs. A
// third gNodeB is added for broader metropolitan NR coverage.
//
package multiratvanet.simulations;

import inet.node.ethernet.Eth10G;
import simu5g.nodes.gNodeB;

network ElectronicCity extends MultiRatHighway
{
    parameters:
        numWifiAps = default(15);
        numDsrcRsus = default(15);
        @display("bgb=1200,700");

    submodules:
        gNodeB3: gNodeB {
            @display("p=560,410;is=vl");
        }

    connections allowunconnected:
        upf.pppg++ <--> Eth10G <--> gNodeB3.ppp;
        gNodeB3.x2++ <--> Eth10G <--> gNodeB2.x2++;
}
