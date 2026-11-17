//
// LatencyQosPolicy.h - choose the in-range RAT that meets a latency budget.
//
// A RAT's latency is half the mean round-trip time of the car's own probes over it. Among
// candidates within 'maxLatencyMs', the one with the highest link rate is selected. If none
// meet the budget, the lowest-latency candidate is used as a best effort. A faster RAT must
// offer 25% more link rate and keep doing so for 'timeToTrigger' seconds.
//
#ifndef MULTIRATVANET_LATENCYQOSPOLICY_H
#define MULTIRATVANET_LATENCYQOSPOLICY_H

#include <cmath>

#include "policies/IRatSelectionPolicy.h"

namespace multiratvanet {

class LatencyQosPolicy : public TimeToTriggerPolicy {
  public:
    explicit LatencyQosPolicy(double maxLatencyMs = 100.0, double timeToTrigger = 1.0)
        : TimeToTriggerPolicy(timeToTrigger), maxLatencyMs_(maxLatencyMs) {}

    RatId prefer(RatId current, const RatMetricsVec &metrics) const override {
        RatId bestWithinBudget = RatId::NONE;
        double bestCap = -1e9;
        RatId lowestLatency = RatId::NONE;
        double minLat = 1e18;

        for (const auto &m : metrics) {
            if (!(m.present && m.inRange))
                continue;
            if (latencyMs(m) < minLat) { minLat = latencyMs(m); lowestLatency = m.id; }
            if (latencyMs(m) <= maxLatencyMs_ && m.linkRateMbps > bestCap) {
                bestCap = m.linkRateMbps;
                bestWithinBudget = m.id;
            }
        }
        RatId best = (bestWithinBudget != RatId::NONE) ? bestWithinBudget : lowestLatency;

        // Stay put if current still satisfies the budget and best is not clearly better.
        if (usable(current, metrics)) {
            const auto &cm = metrics[ratIndex(current)];
            if (latencyMs(cm) <= maxLatencyMs_ &&
                (best == RatId::NONE || metrics[ratIndex(best)].linkRateMbps <= cm.linkRateMbps * 1.25))
                best = current;
        }
        return best;
    }

    const char *name() const override { return "LatencyQos"; }

  private:
    // one-way latency of a RAT as the car knows it: half the mean round trip of its probes
    static double latencyMs(const RatMetrics &m) {
        return std::isnan(m.probeRttMeanMs) ? 1e6 : m.probeRttMeanMs / 2;
    }
    double maxLatencyMs_;
};

} // namespace multiratvanet

#endif
