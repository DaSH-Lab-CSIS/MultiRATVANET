//
// RatStatsCollector - network-wide periodic RAT statistics collector.
//
// A single network-scoped module that samples every `statInterval` and records,
// over all live vehicles: the number of vehicles connected on each active RAT,
// and the network-wide average RSSI proxy per RAT (averaged over the vehicles
// currently in range of that RAT).
//
package multiratvanet;

simple RatStatsCollector
{
    parameters:
        @class(RatStatsCollector);
        @display("i=block/table2");

        double statInterval @unit(s) = default(0.1s); // sampling period
        double startTime @unit(s) = default(0.1s);     // first sample time

        // Number of vehicles whose active RAT is each technology, sampled at statInterval.
        @signal[vehiclesDsrc](type=long);
        @signal[vehiclesWifi](type=long);
        @signal[vehiclesLte](type=long);
        @signal[vehiclesNr](type=long);
        @signal[vehiclesSixg](type=long);
        @signal[vehiclesUnconnected](type=long); // vehicles with no active RAT
        @signal[vehiclesTotal](type=long);       // all live vehicles sampled

        // Network-wide average RSSI proxy (dBm) per RAT, over in-range vehicles.
        @signal[avgRssiDsrc](type=double);
        @signal[avgRssiWifi](type=double);
        @signal[avgRssiLte](type=double);
        @signal[avgRssiNr](type=double);
        @signal[avgRssiSixg](type=double);

        @statistic[vehiclesDsrc](title="vehicles on DSRC"; record=vector,timeavg,max);
        @statistic[vehiclesWifi](title="vehicles on WiFi"; record=vector,timeavg,max);
        @statistic[vehiclesLte](title="vehicles on LTE"; record=vector,timeavg,max);
        @statistic[vehiclesNr](title="vehicles on NR"; record=vector,timeavg,max);
        @statistic[vehiclesSixg](title="vehicles on 6G"; record=vector,timeavg,max);
        @statistic[vehiclesUnconnected](title="vehicles unconnected"; record=vector,timeavg,max);
        @statistic[vehiclesTotal](title="vehicles total"; record=vector,timeavg,max);

        @statistic[avgRssiDsrc](title="avg DSRC RSSI"; unit=dBm; record=vector,mean);
        @statistic[avgRssiWifi](title="avg WiFi RSSI"; unit=dBm; record=vector,mean);
        @statistic[avgRssiLte](title="avg LTE RSSI"; unit=dBm; record=vector,mean);
        @statistic[avgRssiNr](title="avg NR RSSI"; unit=dBm; record=vector,mean);
        @statistic[avgRssiSixg](title="avg 6G RSSI"; unit=dBm; record=vector,mean);
}
