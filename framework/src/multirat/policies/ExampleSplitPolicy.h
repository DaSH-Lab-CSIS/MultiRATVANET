//
// ExampleSplitPolicy.h - an example of a policy written directly against the standard
// request and response, and of choosing a different RAT for each traffic class.
//
// It is a template for new policies, not one of the policies being compared.
//   safety        goes on a short-range RAT (DSRC or WiFi): the one in use while it works,
//                 otherwise the one whose probes come back faster; 5G-NR if neither is usable;
//   infotainment  goes on 5G-NR when it is usable and its probes are getting through, so the
//                 heavy downlink stays off the channel the safety messages use; otherwise it
//                 goes where safety goes.
// A class is moved only after the same different RAT has been the choice for 'holdSeconds':
// the harness applies every answer as given, so not flip-flopping is the policy's own job.
//
#ifndef MULTIRATVANET_EXAMPLESPLITPOLICY_H
#define MULTIRATVANET_EXAMPLESPLITPOLICY_H

#include <cmath>
#include <map>
#include <string>

#include "policies/IRatSelectionPolicy.h"

namespace multiratvanet {

class ExampleSplitPolicy : public IRatSelectionPolicy {
  public:
    explicit ExampleSplitPolicy(double holdSeconds = 1.0) : holdSeconds_(holdSeconds) {}

    PolicyResponse decide(const PolicyRequest &req) override {
        // --- what would be best right now ---
        // short-range RAT for safety: keep the one in use while it works; when choosing anew,
        // DSRC or WiFi, whichever answers probes faster
        RatId current = req.connection.currentRat;
        RatId shortRange = RatId::NONE;
        if ((current == RatId::DSRC || current == RatId::WIFI) && usable(current, req.rats))
            shortRange = current;
        else {
            double bestRtt = 1e18;
            for (RatId r : { RatId::DSRC, RatId::WIFI }) {
                const RatMetrics &m = req.rats[ratIndex(r)];
                if (m.present && m.inRange && !std::isnan(m.probeRttMeanMs) && m.probeRttMeanMs < bestRtt) {
                    bestRtt = m.probeRttMeanMs;
                    shortRange = r;
                }
            }
        }
        const RatMetrics &nr = req.rats[ratIndex(RatId::NR)];
        bool nrGood = nr.present && nr.inRange && !(nr.probeLoss > 0.2);

        RatId wantSafety = shortRange != RatId::NONE ? shortRange : (nrGood ? RatId::NR : firstUsable(req));
        RatId wantInfotainment = nrGood ? RatId::NR : wantSafety;

        // --- move a class only once the same choice has held ---
        PolicyResponse resp;
        resp.rat = settle("", current, wantSafety, req);   // default: where safety goes
        for (const TrafficState &t : req.traffic)
            if (t.trafficClass == "infotainment")
                resp.classRat[t.trafficClass] = settle(t.trafficClass, t.rat, wantInfotainment, req);
        return resp;
    }

    const char *name() const override { return "ExampleSplit"; }

  private:
    struct Pending { RatId rat = RatId::NONE; double since = 0; };

    static RatId firstUsable(const PolicyRequest &req) {
        for (const RatMetrics &m : req.rats)
            if (m.present && m.inRange)
                return m.id;
        return RatId::NONE;
    }

    // 'current' unless 'wanted' has been wanted for holdSeconds (at once if current is unusable).
    // With nothing wanted the answer is NONE: stay (default RAT) / follow the default (a class).
    RatId settle(const std::string &key, RatId current, RatId wanted, const PolicyRequest &req) {
        Pending &p = pending_[key];
        if (wanted == RatId::NONE) {
            p.rat = RatId::NONE;
            return RatId::NONE;
        }
        if (wanted == current) {
            p.rat = RatId::NONE;
            return current;
        }
        if (!usable(current, req.rats)) {
            p.rat = RatId::NONE;
            return wanted;
        }
        if (p.rat != wanted) {
            p.rat = wanted;
            p.since = req.time;
        }
        if (req.time - p.since < holdSeconds_ - 1e-9)
            return current;
        p.rat = RatId::NONE;
        return wanted;
    }

    double holdSeconds_;
    std::map<std::string, Pending> pending_;
};

} // namespace multiratvanet

#endif
