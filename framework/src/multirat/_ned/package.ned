//
// MultiRatVanet - Application-driven multi-RAT (DSRC / WiFi / LTE / 5G-NR / 6G)
// handover framework for OMNeT++ / Veins / INET / Simu5G.
//
// The vehicle node terminates every radio access technology (RAT) at a common
// INET IPv4 network layer (unified-IP architecture). An application-layer
// manager selects the active RAT, subject to a hard "in-range" precondition
// supplied by a per-RAT coverage monitor, and performs the handoff by swapping
// the IPv4 default route (and/or app socket binding). Handover KPIs are emitted
// as signals for post-processing.
//
package multiratvanet;

@namespace(multiratvanet);
