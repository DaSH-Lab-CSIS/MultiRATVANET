//
// IRatSelectionPolicy.h - the interface every RAT selection policy implements.
//
// One policy object belongs to one vehicle. On every decision the simulator calls
// decide() with a PolicyRequest (base/PolicyTypes.h) and uses the RAT in the returned
// PolicyResponse. docs/POLICY_REFERENCE.md is the guide for writing a policy.
//
// A policy MUST only return a RAT that is present and in range in the request (or
// the current RAT, or NONE): the application stack is never switched onto a
// technology that is out of coverage.
//
// TimeToTriggerPolicy, below, is the base of the built-in policies: they state a
// preference (prefer()) and the base turns it into a switch once the preference has
// held for the time-to-trigger.
//
#ifndef MULTIRATVANET_IRATSELECTIONPOLICY_H
#define MULTIRATVANET_IRATSELECTIONPOLICY_H

#include <algorithm>
#include <cstdio>
#include <string>

#include "base/PolicyTypes.h"
#include "base/RatTypes.h"

namespace multiratvanet {

//
// Time-to-trigger, as in LTE/NR handover: a policy's choice of a *different* usable RAT only
// takes effect once the same choice has held for 'seconds'. Losing the current RAT switches at
// once. Without it, cars react to every fade and, worse, all react together to the same load
// change, so they move as a herd and keep swapping RATs.
//
class SwitchConfirmation {
  public:
    explicit SwitchConfirmation(double seconds = 1.0) : seconds_(seconds) {}
    RatId apply(RatId current, RatId wanted, bool currentUsable, const RatMetricsVec &metrics) {
        if (!currentUsable || wanted == RatId::NONE || wanted == current) {
            candidate_ = RatId::NONE;
            return currentUsable && wanted == RatId::NONE ? current : wanted;
        }
        double now = 0;
        for (const auto &m : metrics)
            now = std::max(now, m.lastUpdate);
        if (candidate_ != wanted) {
            candidate_ = wanted;
            since_ = now;
        }
        // tolerance: 'now' is a sum of refresh intervals, so 1.0 s can arrive as 0.9999999
        waited_ = now - since_;
        if (waited_ < seconds_ - 1e-9)
            return current;
        candidate_ = RatId::NONE;
        return wanted;
    }
    void setSeconds(double seconds) { seconds_ = seconds; }
    double seconds() const { return seconds_; }
    RatId pending() const { return candidate_; }  // RAT waiting out the time-to-trigger, or NONE
    double waited() const { return waited_; }     // how long it has been preferred so far (s)
  private:
    double waited_ = 0;
    double seconds_;
    RatId candidate_ = RatId::NONE;
    double since_ = 0;
};

//
// Tunables of the policies (MultiRatAppManager NED parameters).
//
struct PolicyParams {
    double timeToTrigger = 1.0;   // s a better RAT must stay preferred before the switch
    double sinrMarginDb = 3.0;    // Sinr: SINR-margin gain needed to prefer another RAT
    double loadMargin = 0.15;     // Load: load reduction needed to prefer another RAT
    double maxLatencyMs = 100.0;  // LatencyQos: latency budget
};

class IRatSelectionPolicy {
  public:
    virtual ~IRatSelectionPolicy() {}

    // Decide which RAT this vehicle uses from now on. Called once per decision interval.
    virtual PolicyResponse decide(const PolicyRequest &request) = 0;

    // The vehicle has left the simulation (or the run ended). 'last' is its final state; no
    // response is expected. For learning policies, to close an episode.
    virtual void vehicleLeft(const PolicyRequest &last) {}

    // Human-readable policy name (used in logs and statistics).
    virtual const char *name() const = 0;

    // True if 'r' is a usable (present + in range) RAT in 'metrics'.
    static bool usable(RatId r, const RatMetricsVec &metrics) {
        if (r == RatId::NONE)
            return false;
        int i = ratIndex(r);
        if (i < 0 || i >= (int)metrics.size())
            return false;
        return metrics[i].present && metrics[i].inRange;
    }

    // The RATs that are present and in range.
    static std::vector<RatId> candidates(const RatMetricsVec &metrics) {
        std::vector<RatId> out;
        for (const auto &m : metrics)
            if (m.present && m.inRange)
                out.push_back(m.id);
        return out;
    }
};

//
// Base of the built-in policies. A subclass says which RAT it would use right now (prefer());
// this class makes the switch only after the same different RAT has been preferred for the
// time-to-trigger. Both look at the current RAT and the per-RAT measurements only.
//
class TimeToTriggerPolicy : public IRatSelectionPolicy {
  public:
    explicit TimeToTriggerPolicy(double timeToTrigger = 1.0) : confirm_(timeToTrigger) {}

    // The RAT this policy would use right now, before time-to-trigger: the current RAT unless
    // another one is better by the policy's own margin. Keeps no state, so it can be asked at
    // any time (EnsemblePolicy asks every member on every decision).
    virtual RatId prefer(RatId current, const RatMetricsVec &metrics) const = 0;

    // Decide the RAT to be active. 'current' may be RatId::NONE at startup. A preference for a
    // different usable RAT takes effect once it has held for the time-to-trigger.
    virtual RatId select(RatId current, const RatMetricsVec &metrics) {
        return confirm_.apply(current, prefer(current, metrics), usable(current, metrics), metrics);
    }

    PolicyResponse decide(const PolicyRequest &request) override {
        RatId current = request.connection.currentRat;
        RatId wanted = prefer(current, request.rats);
        PolicyResponse response(select(current, request.rats));
        explain(response, current, wanted, request.rats);
        return response;
    }

  protected:
    // Why the decision came out as it did, for the decision log (PolicyResponse::branch/reason):
    //   none   no usable RAT          start  first connection     lost  current RAT stopped working
    //   best   already on the top pick                            margin top pick not better by enough
    //   wait   better RAT, time-to-trigger still running          switch better for long enough
    // The top pick is prefer() without a current RAT, i.e. before the policy's keep-current rule.
    virtual void explain(PolicyResponse &out, RatId current, RatId wanted, const RatMetricsVec &metrics) const {
        bool currentUsable = usable(current, metrics);
        if (wanted == RatId::NONE && !currentUsable)
            out.branch = "none";
        else if (current == RatId::NONE)
            out.branch = "start";
        else if (!currentUsable)
            out.branch = "lost";
        else if (wanted == current || wanted == RatId::NONE) {
            RatId top = prefer(RatId::NONE, metrics);
            if (top == current || top == RatId::NONE || !usable(top, metrics))
                out.branch = "best";
            else {
                out.branch = "margin";
                std::string note = marginNote(current, top, metrics);
                out.reason = std::string(ratName(top)) + (note.empty() ? "" : " " + note);
            }
        }
        else if (out.rat == current || out.rat == RatId::NONE) {
            out.branch = "wait";
            char buf[64];
            if (confirm_.pending() == wanted)
                snprintf(buf, sizeof buf, "%s for %.1f of %.1f s", ratName(wanted), confirm_.waited(), confirm_.seconds());
            else
                snprintf(buf, sizeof buf, "%s", ratName(wanted));
            out.reason = buf;
        }
        else
            out.branch = "switch";
    }

    // For a "margin" outcome: how much better the top pick was and what the policy needs, e.g.
    // "+1.2 dB, needs +3".
    virtual std::string marginNote(RatId current, RatId top, const RatMetricsVec &metrics) const { return ""; }


    SwitchConfirmation confirm_;
};

} // namespace multiratvanet

#endif
