//
// SixGInterface - 6G placeholder radio interface.
//
// This is an intentional STUB so the framework already has a slot for a 6G RAT.
// It reuses INET's Ieee80211Interface with 6G-flavoured defaults (very wide
// channel, high carrier frequency, short range) purely as a stand-in. Replace
// the internals with a dedicated 6G PHY/MAC model when one becomes available;
// the rest of the framework (RatId::SIXG, coverage monitor, app manager,
// policies) already treats it as a first-class RAT.
//
package multiratvanet;

import inet.linklayer.ieee80211.Ieee80211Interface;

module SixGInterface extends Ieee80211Interface
{
    parameters:
        @display("i=block/ifcard;bgb=,,#f0e0ff");
        // Placeholder 6G-like PHY settings (approximation via 802.11 model).
        radio.typename = default("Ieee80211ScalarRadio");
        radio.centerFrequency = default(100GHz);
        radio.bandwidth = default(400MHz);
        radio.transmitter.power = default(0.05W); // low power, short range
        mac.typename = default("Ieee80211Mac");
}
