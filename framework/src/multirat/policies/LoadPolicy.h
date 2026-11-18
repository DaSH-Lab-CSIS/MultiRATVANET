//
// LoadPolicy.h - load-balancing selection: choose the least-loaded in-range RAT.
//
// Load is what the car's own radio senses: the 802.11 channel busy ratio of DSRC and WiFi. A
// car cannot see how loaded a cell is, so cellular has no load figure and is used only when
// neither DSRC nor WiFi is usable. A less loaded RAT must beat the current one by 'marginLoad'
// for 'timeToTrigger' seconds: every car senses much the same load, so without that wait they
// all move at once and swap the load around.
//
#ifndef MULTIRATVANET_LOADPOLICY_H
#define MULTIRATVANET_LOADPOLICY_H

#include <cmath>

#include "policies/IRatSelectionPolicy.h"

namespace multiratvanet {

class LoadPolicy : public TimeToTriggerPolicy {
  public:
    explicit LoadPolicy(double marginLoad = 0.15, double timeToTrigger = 1.0)
        : TimeToTriggerPolicy(timeToTrigger), marginLoad_(marginLoad) {}

    RatId prefer(RatId current, const RatMetricsVec &metrics) const override {
        // least-loaded RAT among those whose load the car can sense (DSRC, WiFi)
        RatId best = RatId::NONE;
        double bestLoad = 1e18;
        for (const auto &m : metrics) {
            if (m.present && m.inRange && !std::isnan(m.load) && m.load < bestLoad) {
                bestLoad = m.load;
                best = m.id;
            }
        }
        if (best == RatId::NONE) {
            // none of them usable: a RAT without a load figure (cellular) is the fallback
            if (usable(current, metrics))
                return current;
            for (const auto &m : metrics)
                if (m.present && m.inRange)
                    return m.id;
            return RatId::NONE;
        }
        // stay unless the best is clearly less loaded; a current RAT without a load figure is
        // left as soon as a sensed one is usable
        if (usable(current, metrics)) {
            double currentLoad = metrics[ratIndex(current)].load;
            if (!std::isnan(currentLoad) && bestLoad > currentLoad - marginLoad_)
                best = current;
        }
        return best;
    }

    const char *name() const override { return "Load"; }

  protected:
    std::string marginNote(RatId current, RatId top, const RatMetricsVec &metrics) const override {
        double c = metrics[ratIndex(current)].load, t = metrics[ratIndex(top)].load;
        if (std::isnan(c) || std::isnan(t))
            return "";
        char buf[48];
        snprintf(buf, sizeof buf, "%.0f%% less busy, needs %.0f%%", (c - t) * 100, marginLoad_ * 100);
        return buf;
    }

  private:
    double marginLoad_;
};

} // namespace multiratvanet

#endif
