//
// SinrPolicy.h - pick the in-range RAT with the best radio quality.
//
// RATs are compared by their SINR margin (sinrDb - minSinrDb): how far each is above
// the lowest SINR it can still use. Raw SINR is not comparable across technologies
// (802.11 at 24 Mbit/s needs ~10 dB, NR works at -5 dB). A better RAT must beat the
// current one by 'marginDb' and keep doing so for 'timeToTrigger' seconds before the
// switch, like the A3 event in LTE/NR handover; this stops ping-pong on fades and
// short interference. If the current RAT is lost, the best one is taken at once.
//
#ifndef MULTIRATVANET_SINRPOLICY_H
#define MULTIRATVANET_SINRPOLICY_H

#include "policies/IRatSelectionPolicy.h"

namespace multiratvanet {

class SinrPolicy : public TimeToTriggerPolicy {
  public:
    explicit SinrPolicy(double marginDb = 3.0, double timeToTrigger = 1.0)
        : TimeToTriggerPolicy(timeToTrigger), marginDb_(marginDb) {}

    RatId prefer(RatId current, const RatMetricsVec &metrics) const override {
        RatId best = RatId::NONE;
        double bestMargin = -1e9;
        for (const auto &m : metrics) {
            if (m.present && m.inRange && m.sinrDb - m.minSinrDb > bestMargin) {
                bestMargin = m.sinrDb - m.minSinrDb;
                best = m.id;
            }
        }
        if (usable(current, metrics)) {
            const auto &cm = metrics[ratIndex(current)];
            if (bestMargin < cm.sinrDb - cm.minSinrDb + marginDb_)
                best = current; // not enough gain to justify a switch
        }
        return best;
    }

    const char *name() const override { return "Sinr"; }

  private:
    double marginDb_;
};

} // namespace multiratvanet

#endif
