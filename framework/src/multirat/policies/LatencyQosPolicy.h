//
// LatencyQosPolicy.h - choose the in-range RAT that meets a latency budget.
//
// Among candidates whose estimated latency is within 'maxLatencyMs', the one
// with the highest estimated capacity is selected. If none meet the budget, the
// lowest-latency candidate is used as a best effort.
//
#ifndef MULTIRATVANET_LATENCYQOSPOLICY_H
#define MULTIRATVANET_LATENCYQOSPOLICY_H

#include "policies/IRatSelectionPolicy.h"

namespace multiratvanet {

class LatencyQosPolicy : public IRatSelectionPolicy {
  public:
    explicit LatencyQosPolicy(double maxLatencyMs = 100.0)
        : maxLatencyMs_(maxLatencyMs) {}

    RatId select(RatId current, const RatMetricsVec &metrics) override {
        RatId bestWithinBudget = RatId::NONE;
        double bestCap = -1e9;
        RatId lowestLatency = RatId::NONE;
        double minLat = 1e18;

        for (const auto &m : metrics) {
            if (!(m.present && m.inRange))
                continue;
            if (m.estLatencyMs < minLat) { minLat = m.estLatencyMs; lowestLatency = m.id; }
            if (m.estLatencyMs <= maxLatencyMs_ && m.capacityMbps > bestCap) {
                bestCap = m.capacityMbps;
                bestWithinBudget = m.id;
            }
        }
        RatId best = (bestWithinBudget != RatId::NONE) ? bestWithinBudget : lowestLatency;

        // Stay put if current still satisfies the budget and best is not clearly better.
        if (usable(current, metrics)) {
            const auto &cm = metrics[ratIndex(current)];
            if (cm.estLatencyMs <= maxLatencyMs_ &&
                (best == RatId::NONE || metrics[ratIndex(best)].capacityMbps <= cm.capacityMbps * 1.1))
                return current;
        }
        return best;
    }

    const char *name() const override { return "LatencyQos"; }

  private:
    double maxLatencyMs_;
};

} // namespace multiratvanet

#endif
