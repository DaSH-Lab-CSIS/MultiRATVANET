//
// LoadPolicy.h - load-balancing selection: choose the least-loaded in-range RAT.
//
#ifndef MULTIRATVANET_LOADPOLICY_H
#define MULTIRATVANET_LOADPOLICY_H

#include "policies/IRatSelectionPolicy.h"

namespace multiratvanet {

class LoadPolicy : public IRatSelectionPolicy {
  public:
    explicit LoadPolicy(double marginLoad = 0.15) : marginLoad_(marginLoad) {}

    RatId select(RatId current, const RatMetricsVec &metrics) override {
        RatId best = RatId::NONE;
        double bestLoad = 1e18;
        for (const auto &m : metrics) {
            if (m.present && m.inRange && m.load < bestLoad) {
                bestLoad = m.load;
                best = m.id;
            }
        }
        if (usable(current, metrics)) {
            double cur = metrics[ratIndex(current)].load;
            if (bestLoad > cur - marginLoad_)
                return current;
        }
        return best;
    }

    const char *name() const override { return "Load"; }

  private:
    double marginLoad_;
};

} // namespace multiratvanet

#endif
