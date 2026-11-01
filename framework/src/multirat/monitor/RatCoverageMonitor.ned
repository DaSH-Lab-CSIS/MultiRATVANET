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

        // Where per-RAT signal and coverage come from:
        //   "measured": the radios themselves. 802.11: power and SNIR of beacons received from
        //               this RAT's infrastructure (RSU/AP); cellular: Simu5G downlink SINR of the
        //               serving cell. A RAT is in range while it has been measured within
        //               measurementMaxAge and is above its threshold (dsrc/wifiRssiThreshold,
        //               lte/nrMinSinr). The *Range parameters and the path-loss proxy are unused.
        //   "proxy":    distance to the nearest infrastructure node and a log-distance path-loss
        //               estimate (the original behaviour; RATs with no infraType are always in range).
        string signalSource = default("measured");
        double measurementMaxAge @unit(s) = default(0.5s);
        double lteMinSinr @unit(dB) = default(-5dB);
        double nrMinSinr @unit(dB) = default(-5dB);
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
