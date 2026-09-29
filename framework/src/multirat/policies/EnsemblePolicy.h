//
// EnsemblePolicy.h - consult all base policies and vote on a single RAT.
//
// Each constituent policy (CoveragePriority, Sinr, LatencyQos, Load) independently
// proposes an in-range RAT; the ensemble tallies the weighted votes and elects the
// RAT with the most support. Per-voter weights are configurable (0 disables a
// voter). Because every base policy already enforces the inRange precondition, the
// precondition, the elected RAT is always usable. A hysteresis rule keeps the
// current RAT when its vote is within a margin of the leader (suppressing
// ping-pong on near-ties), and any remaining tie is broken by coverage priority.
//
// The Ml policy is intentionally NOT a voter: it is an external FL/ML hook whose
// unfed default merely mirrors CoveragePriority, which would double-weight it.
//
#ifndef MULTIRATVANET_ENSEMBLEPOLICY_H
#define MULTIRATVANET_ENSEMBLEPOLICY_H

#include <memory>
#include <vector>
#include "policies/IRatSelectionPolicy.h"
#include "policies/CoveragePriorityPolicy.h"
#include "policies/SinrPolicy.h"
#include "policies/LatencyQosPolicy.h"
#include "policies/LoadPolicy.h"

namespace multiratvanet {

class EnsemblePolicy : public IRatSelectionPolicy {
  public:
    explicit EnsemblePolicy(double stickiness = 1.0) : stickiness_(stickiness) {
        // Order matters: it maps 1:1 to the weights_ vector and setWeights().
        members_.emplace_back(new CoveragePriorityPolicy()); // weights_[0]
        members_.emplace_back(new SinrPolicy());             // weights_[1]
        members_.emplace_back(new LatencyQosPolicy());       // weights_[2]
        members_.emplace_back(new LoadPolicy());             // weights_[3]
        weights_.assign(members_.size(), 1.0);
    }

    // Set per-voter weights (0 disables a voter). Order: coverage, sinr, latency, load.
    void setWeights(double coverage, double sinr, double latency, double load) {
        weights_ = { coverage, sinr, latency, load };
        weights_.resize(members_.size(), 1.0);
    }
    void setStickiness(double s) { stickiness_ = s; }

    RatId select(RatId current, const RatMetricsVec &metrics) override {
        double votes[(int)RatId::COUNT] = {0};
        bool anyVote = false;
        for (size_t k = 0; k < members_.size(); ++k) {
            if (weights_[k] <= 0.0)
                continue; // voter disabled
            RatId r = members_[k]->select(current, metrics);
            if (usable(r, metrics)) {
                votes[ratIndex(r)] += weights_[k];
                anyVote = true;
            }
        }
        if (!anyVote)
            return RatId::NONE; // no usable RAT proposed; keep whatever we had

        // Leader = highest vote count.
        double bestVotes = 0.0;
        for (int i = 0; i < (int)RatId::COUNT; ++i)
            if (votes[i] > bestVotes) bestVotes = votes[i];

        // Tie-break by coverage priority: first RAT in this order holding the max.
        static const RatId order[] = {
            RatId::DSRC, RatId::WIFI, RatId::NR, RatId::LTE, RatId::SIXG
        };
        RatId best = RatId::NONE;
        for (RatId r : order)
            if (votes[ratIndex(r)] == bestVotes) { best = r; break; }

        // Hysteresis: keep the current RAT if still usable and its vote is within
        // 'stickiness_' of the leader (avoids switching on marginal vote splits).
        if (usable(current, metrics)) {
            double cur = votes[ratIndex(current)];
            if (cur >= bestVotes - stickiness_)
                return current;
        }
        return best;
    }

    const char *name() const override { return "Ensemble"; }

  private:
    std::vector<std::unique_ptr<IRatSelectionPolicy>> members_;
    std::vector<double> weights_; // parallel to members_ (coverage, sinr, latency, load)
    double stickiness_; // votes within this margin of the leader keep current
};

} // namespace multiratvanet

#endif
