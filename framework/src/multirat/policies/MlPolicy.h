//
// MlPolicy.h - hook for a learned / externally-driven RAT selection.
//
// This is the integration point for a machine-learning or federated-learning
// controller. An external component (e.g., an FL agent) writes a suggestion via
// suggest(); the policy honours it only when that RAT is in range, otherwise it
// falls back to a coverage-priority decision. This keeps the ML output safe: it
// can never select an out-of-coverage technology.
//
#ifndef MULTIRATVANET_MLPOLICY_H
#define MULTIRATVANET_MLPOLICY_H

#include "policies/IRatSelectionPolicy.h"
#include "policies/CoveragePriorityPolicy.h"

namespace multiratvanet {

class MlPolicy : public IRatSelectionPolicy {
  public:
    MlPolicy() : fallback_() {}

    // Called by the external ML/FL controller between decisions.
    void suggest(RatId r) { suggested_ = r; }

    RatId select(RatId current, const RatMetricsVec &metrics) override {
        if (usable(suggested_, metrics))
            return suggested_;
        return fallback_.select(current, metrics);
    }

    const char *name() const override { return "Ml"; }

  private:
    RatId suggested_ = RatId::NONE;
    CoveragePriorityPolicy fallback_;
};

} // namespace multiratvanet

#endif
