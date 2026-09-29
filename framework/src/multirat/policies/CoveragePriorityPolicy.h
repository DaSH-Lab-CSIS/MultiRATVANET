//
// CoveragePriorityPolicy.h - pick the highest-priority RAT that is in range.
//
// A fixed preference order is scanned and the first present + in-range RAT is
// chosen. A small "stickiness" rule keeps the current RAT if it is still usable
// and of equal-or-higher priority than the best alternative, which suppresses
// needless ping-pong at coverage borders.
//
#ifndef MULTIRATVANET_COVERAGEPRIORITYPOLICY_H
#define MULTIRATVANET_COVERAGEPRIORITYPOLICY_H

#include "policies/IRatSelectionPolicy.h"

namespace multiratvanet {

class CoveragePriorityPolicy : public IRatSelectionPolicy {
  public:
    explicit CoveragePriorityPolicy(std::vector<RatId> order = defaultOrder())
        : order_(std::move(order)) {}

    static std::vector<RatId> defaultOrder() {
        return { RatId::DSRC, RatId::WIFI, RatId::NR, RatId::LTE, RatId::SIXG };
    }

    RatId select(RatId current, const RatMetricsVec &metrics) override {
        RatId best = RatId::NONE;
        for (RatId r : order_) {
            if (usable(r, metrics)) { best = r; break; }
        }
        // Stickiness: stay on current if still usable and not worse than best.
        if (usable(current, metrics) && rank(current) <= rank(best))
            return current;
        return best;
    }

    const char *name() const override { return "CoveragePriority"; }

  private:
    int rank(RatId r) const {
        for (size_t i = 0; i < order_.size(); ++i)
            if (order_[i] == r) return (int)i;
        return (int)order_.size() + 1;
    }
    std::vector<RatId> order_;
};

} // namespace multiratvanet

#endif
