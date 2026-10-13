//
// IRatSelectionPolicy.h - strategy interface for choosing the active RAT.
//
// A policy is handed the current RAT and the full per-RAT metric vector, and
// returns the RAT that should be active. Implementations MUST only ever return
// a RAT whose metrics report inRange==true (or the current RAT, or NONE); the
// in-range flag is a hard precondition enforced by every policy so that the
// application stack never switches onto a technology that is out of coverage.
//
#ifndef MULTIRATVANET_IRATSELECTIONPOLICY_H
#define MULTIRATVANET_IRATSELECTIONPOLICY_H

#include "base/RatTypes.h"

namespace multiratvanet {

class IRatSelectionPolicy {
  public:
    virtual ~IRatSelectionPolicy() {}

    // Decide the RAT to be active. 'current' may be RatId::NONE at startup.
    virtual RatId select(RatId current, const RatMetricsVec &metrics) = 0;

    // Human-readable policy name (used in logs and statistics).
    virtual const char *name() const = 0;

  protected:
    // Convenience: collect the RATs that are present and in range.
    static std::vector<RatId> candidates(const RatMetricsVec &metrics) {
        std::vector<RatId> out;
        for (const auto &m : metrics)
            if (m.present && m.inRange)
                out.push_back(m.id);
        return out;
    }

    // True if 'r' is currently a usable (present + in range) candidate.
    static bool usable(RatId r, const RatMetricsVec &metrics) {
        if (r == RatId::NONE)
            return false;
        int i = ratIndex(r);
        if (i < 0 || i >= (int)metrics.size())
            return false;
        return metrics[i].present && metrics[i].inRange;
    }
};

} // namespace multiratvanet

#endif
