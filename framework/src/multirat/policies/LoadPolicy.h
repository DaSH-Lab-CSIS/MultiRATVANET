//
// LoadPolicy.h - load-balancing selection: choose the least-loaded in-range RAT.
//
// Load is measured (802.11 channel busy ratio, cellular resource-block utilisation). A less
// loaded RAT must beat the current one by 'marginLoad' for 'timeToTrigger' seconds: every car
// sees the same load, so without that wait they all move at once and swap the load around.
//
#ifndef MULTIRATVANET_LOADPOLICY_H
#define MULTIRATVANET_LOADPOLICY_H

#include "policies/IRatSelectionPolicy.h"

namespace multiratvanet {

class LoadPolicy : public IRatSelectionPolicy {
  public:
    explicit LoadPolicy(double marginLoad = 0.15, double timeToTrigger = 1.0)
        : marginLoad_(marginLoad), confirm_(timeToTrigger) {}

    RatId select(RatId current, const RatMetricsVec &metrics) override {
        RatId best = RatId::NONE;
        double bestLoad = 1e18;
        for (const auto &m : metrics) {
            if (m.present && m.inRange && m.load < bestLoad) {
                bestLoad = m.load;
                best = m.id;
            }
        }
        bool currentUsable = usable(current, metrics);
        if (currentUsable && bestLoad > metrics[ratIndex(current)].load - marginLoad_)
            best = current;
        return confirm_.apply(current, best, currentUsable, metrics);
    }

    const char *name() const override { return "Load"; }

  private:
    double marginLoad_;
    SwitchConfirmation confirm_;
};

} // namespace multiratvanet

#endif
