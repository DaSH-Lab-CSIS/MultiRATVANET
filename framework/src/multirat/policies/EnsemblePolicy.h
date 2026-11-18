//
// EnsemblePolicy.h - consult all base policies and vote on a single RAT.
//
// Each constituent policy (CoveragePriority, Sinr, LatencyQos, Load) independently
// says which in-range RAT it prefers right now (prefer(): its own margins applied,
// no time-to-trigger); the ensemble tallies the weighted votes and elects the RAT
// with the most support. Per-voter weights are configurable (0 disables a voter).
// Because every base policy already enforces the inRange precondition, the elected
// RAT is always usable. A hysteresis rule keeps the current RAT when its vote is
// within a margin of the leader (suppressing ping-pong on near-ties), and any
// remaining tie is broken by coverage priority.
//
// Time-to-trigger is applied once, to the outcome of the vote. The members' own
// timers are not used: each would reset the moment its vote was cast, so voters whose
// preferences began at different times would never be counted together.
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

class EnsemblePolicy : public TimeToTriggerPolicy {
  public:
    explicit EnsemblePolicy(double stickiness = 1.0, const PolicyParams &p = PolicyParams())
        : TimeToTriggerPolicy(p.timeToTrigger), stickiness_(stickiness) {
        // Order matters: it maps 1:1 to the weights_ vector and setWeights().
        members_.emplace_back(new CoveragePriorityPolicy());       // weights_[0]
        members_.emplace_back(new SinrPolicy(p.sinrMarginDb));     // weights_[1]
        members_.emplace_back(new LatencyQosPolicy(p.maxLatencyMs)); // weights_[2]
        members_.emplace_back(new LoadPolicy(p.loadMargin));       // weights_[3]
        weights_.assign(members_.size(), 1.0);
    }

    // Set per-voter weights (0 disables a voter). Order: coverage, sinr, latency, load.
    void setWeights(double coverage, double sinr, double latency, double load) {
        weights_ = { coverage, sinr, latency, load };
        weights_.resize(members_.size(), 1.0);
    }
    void setStickiness(double s) { stickiness_ = s; }

    RatId prefer(RatId current, const RatMetricsVec &metrics) const override {
        double votes[(int)RatId::COUNT];
        return vote(current, metrics, votes);
    }

    const char *name() const override { return "Ensemble"; }

  protected:
    void explain(PolicyResponse &out, RatId current, RatId wanted, const RatMetricsVec &metrics) const override {
        double votes[(int)RatId::COUNT];
        vote(current, metrics, votes);
        TimeToTriggerPolicy::explain(out, current, wanted, metrics);
        if (out.branch == "margin")  // kept although another RAT leads: within the stickiness
            out.branch = "sticky";
        std::string tally;
        for (int i = 0; i < (int)RatId::COUNT; ++i)
            if (votes[i] > 0) {
                char buf[32];
                snprintf(buf, sizeof buf, "%s%s %g", tally.empty() ? "votes: " : "; ", ratName((RatId)i), votes[i]);
                tally += buf;
            }
        if (out.branch == "sticky" || out.branch == "best")
            out.reason = tally;
        else if (!tally.empty())
            out.reason += (out.reason.empty() ? "" : "; ") + tally;
    }

  private:
    // Each member names the RAT it prefers now; returns the RAT to use (leader, or current within
    // the stickiness) and fills 'votes' (indexed by RatId).
    RatId vote(RatId current, const RatMetricsVec &metrics, double *votes) const {
        std::fill(votes, votes + (int)RatId::COUNT, 0.0);
        bool anyVote = false;
        for (size_t k = 0; k < members_.size(); ++k) {
            if (weights_[k] <= 0.0)
                continue; // voter disabled
            RatId r = members_[k]->prefer(current, metrics);
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

    std::vector<std::unique_ptr<TimeToTriggerPolicy>> members_;
    std::vector<double> weights_; // parallel to members_ (coverage, sinr, latency, load)
    double stickiness_; // votes within this margin of the leader keep current
};

} // namespace multiratvanet

#endif
