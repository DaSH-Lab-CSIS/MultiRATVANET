//
// RatCoverageMonitor - per-RAT coverage / range detection.
//
// Periodically estimates, for every radio access technology on the vehicle,
// whether the node is within usable coverage ("in range"). Coverage is derived
// from the distance to the nearest matching infrastructure node (RSU / AP / gNB)
// and a log-distance path-loss RSSI proxy compared against a per-RAT threshold.
// The resulting per-RAT metrics feed the MultiRatAppManager, and enter/leave
// range transitions are emitted as signals for statistics.
//
package multiratvanet;

simple RatCoverageMonitor
{
    parameters:
        @class(RatCoverageMonitor);
        @display("i=block/cogwheel");

        double updateInterval @unit(s) = default(0.1s);

        // Where per-RAT metrics come from:
        //   "measured": the running simulation (see RatCoverageMonitor.h). signal = estimated uplink
        //               SINR: SNIR of beacons from the associated RSU/AP, or Simu5G downlink SINR,
        //               minus the transmit-power difference between infrastructure and car;
        //               load = 802.11 channel busy ratio, serving cell uplink RB utilisation;
        //               capacity = link rate x free share; latency = path latency + service
        //               time / (1 - load). In range = measured within measurementMaxAge, filtered
        //               SINR >= the RAT's *MinSinr (+inRangeHysteresis to enter), and for 802.11
        //               associated. The *Range, *RssiThreshold, path-loss and *LatencyMs /
        //               *CapacityMbps parameters are not used.
        //   "proxy":    distance to the nearest infrastructure node, a log-distance path-loss
        //               estimate and the fixed *LatencyMs / *CapacityMbps numbers (the original
        //               behaviour; RATs with no infraType are always in range).
        string signalSource = default("measured");
        double measurementMaxAge @unit(s) = default(0.5s);
        double dsrcMinSinr @unit(dB) = default(10dB);  // 802.11g 24 Mbit/s data rate needs about this
        double wifiMinSinr @unit(dB) = default(10dB);
        double lteMinSinr @unit(dB) = default(-5dB);
        double nrMinSinr @unit(dB) = default(-5dB);
        double inRangeHysteresis @unit(dB) = default(2dB); // extra SINR needed to enter range
        double filterWeight = default(0.5);   // weight of the newest sample (signal and load filters)
        // Fixed parts of latency the metrics cannot see: 802.11 channel access, cellular
        // scheduling request/grant cycle. Reference packet size for the service time.
        double wlanPathLatency @unit(s) = default(0.2ms);
        double cellularPathLatency @unit(s) = default(4ms);
        int latencyReferencePacket @unit(B) = default(1250B);
        string dsrcNic = default("wlan[0]");   // car NIC whose radio carries DSRC / WiFi
        string wifiNic = default("wlan[1]");
        bool useDistance = default(true);   // gate coverage on distance <= range
        bool useSignal = default(true);     // gate coverage on rssiProxy >= threshold

        // Which RATs are equipped on this node.
        bool hasDsrc = default(true);
        bool hasWifi = default(true);
        bool hasLte  = default(true);
        bool hasNr   = default(true);
        bool hasSixG = default(false);

        // Coverage radius per RAT.
        double dsrcRange @unit(m) = default(300m);
        double wifiRange @unit(m) = default(200m);
        double lteRange  @unit(m) = default(2000m);
        double nrRange   @unit(m) = default(600m);
        double sixgRange @unit(m) = default(150m);

        // Minimum RSSI proxy (dBm) to consider a RAT usable.
        double dsrcRssiThreshold @unit(dBm) = default(-90dBm);
        double wifiRssiThreshold @unit(dBm) = default(-82dBm);
        double lteRssiThreshold  @unit(dBm) = default(-100dBm);
        double nrRssiThreshold   @unit(dBm) = default(-95dBm);
        double sixgRssiThreshold @unit(dBm) = default(-88dBm);

        // Simple log-distance path-loss RSSI proxy parameters.
        double txPowerDbm = default(23.0);       // reference EIRP of infra
        double pathLossExponent = default(2.5);
        double referenceLossDb = default(40.0);  // loss at 1 m

        // Nominal QoS proxies per RAT (used by QoS/latency/load policies).
        double dsrcLatencyMs = default(5.0);   double dsrcCapacityMbps = default(6.0);
        double wifiLatencyMs = default(12.0);  double wifiCapacityMbps = default(50.0);
        double lteLatencyMs  = default(50.0);  double lteCapacityMbps  = default(75.0);
        double nrLatencyMs   = default(20.0);  double nrCapacityMbps   = default(300.0);
        double sixgLatencyMs = default(1.0);   double sixgCapacityMbps = default(1000.0);

        // Infrastructure discovery: a module is treated as infrastructure for a
        // RAT if its NED type simple name contains the given (case-insensitive)
        // marker. Empty string disables discovery for that RAT (always in range
        // when equipped, e.g. for an idealized cellular umbrella).
        string dsrcInfraType = default("Rsu");
        string wifiInfraType = default("AccessPoint");
        string lteInfraType  = default("eNodeB");
        string nrInfraType   = default("gNodeB");
        string sixgInfraType = default("");

        // Signals: per-RAT in-range boolean (1/0) and current RSSI proxy.
        @signal[dsrcInRange](type=long);  @signal[dsrcRssi](type=double);
        @signal[wifiInRange](type=long);  @signal[wifiRssi](type=double);
        @signal[lteInRange](type=long);   @signal[lteRssi](type=double);
        @signal[nrInRange](type=long);    @signal[nrRssi](type=double);
        @signal[sixgInRange](type=long);  @signal[sixgRssi](type=double);
        @signal[coverageCount](type=long); // number of RATs currently in range
        @signal[connectivity](type=long);  // 1 while >=1 RAT usable, else 0
        @signal[outageEvent](type=long);   // pulse (1) at the start of each outage

        @statistic[dsrcInRange](record=timeavg,vector);
        @statistic[wifiInRange](record=timeavg,vector);
        @statistic[lteInRange](record=timeavg,vector);
        @statistic[nrInRange](record=timeavg,vector);
        @statistic[sixgInRange](record=timeavg,vector);
        @statistic[coverageCount](record=timeavg,vector,max);
        @statistic[connectivity](record=timeavg,vector);
        @statistic[outageEvent](record=count);
}
