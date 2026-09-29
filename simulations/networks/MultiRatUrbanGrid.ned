//
// MultiRatUrbanGrid - denser urban baseline.
//
// Keeps the same validated core wiring as MultiRatHighway, and only scales
// WiFi/DSRC roadside infrastructure density for urban blocks.
//
package multiratvanet.simulations;

network MultiRatUrbanGrid extends MultiRatHighway
{
    parameters:
        numWifiAps = default(10);
        numDsrcRsus = default(10);
        @display("bgb=1100,650");
}
