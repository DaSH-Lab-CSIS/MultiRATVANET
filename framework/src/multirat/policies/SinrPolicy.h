//
// SinrPolicy.h - pick the in-range RAT with the best radio quality (SINR).
//
// Uses a hysteresis margin: the current RAT is retained unless another
// candidate's SINR exceeds it by more than 'marginDb', which limits ping-pong.
//
#ifndef MULTIRATVANET_SINRPOLICY_H
#define MULTIRATVANET_SINRPOLICY_H

#include "policies/IRatSelectionPolicy.h"

namespace multiratvanet {

class SinrPolicy : public IRatSelectionPolicy {
  public:
    explicit SinrPolicy(double marginDb = 3.0) : marginDb_(marginDb) {}

    RatId select(RatId current, const RatMetricsVec &metrics) override {
        RatId best = RatId::NONE;
        double bestSinr = -1e9;
        for (const auto &m : metrics) {
            if (m.present && m.inRange && m.sinrDb > bestSinr) {
                bestSinr = m.sinrDb;
                best = m.id;
            }
        }
        if (usable(current, metrics)) {
            double cur = metrics[ratIndex(current)].sinrDb;
            if (bestSinr < cur + marginDb_)
                return current; // not enough gain to justify a handover
        }
        return best;
    }

    const char *name() const override { return "Sinr"; }

  private:
    double marginDb_;
};

} // namespace multiratvanet

#endif
