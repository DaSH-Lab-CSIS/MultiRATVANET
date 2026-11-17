//
// SingleRatPolicy.h - a baseline: the car uses one RAT and nothing else ("OnlyDsrc", "OnlyWifi",
// "OnlyNr").
//
// It asks for its RAT whenever that RAT is usable and never names another one. Once attached,
// the car stays on that RAT; while it is out of range the car's traffic still goes out on it
// and is lost, as it would be for a car that has only that radio. Probes still run on every
// linked RAT, so the channels carry the same probe load as in the runs of the real policies.
//
// Used by the test bench (bench/) to show what each RAT gives on its own.
//
#ifndef MULTIRATVANET_SINGLERATPOLICY_H
#define MULTIRATVANET_SINGLERATPOLICY_H

#include <string>

#include "policies/IRatSelectionPolicy.h"

namespace multiratvanet {

class SingleRatPolicy : public IRatSelectionPolicy {
  public:
    explicit SingleRatPolicy(RatId rat, const char *name) : rat_(rat), name_(name) {}

    PolicyResponse decide(const PolicyRequest &req) override {
        PolicyResponse resp;
        resp.rat = usable(rat_, req.rats) ? rat_ : RatId::NONE; // NONE: keep what we have
        return resp;
    }

    const char *name() const override { return name_.c_str(); }

  private:
    RatId rat_;
    std::string name_;
};

} // namespace multiratvanet

#endif
