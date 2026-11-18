//
// RatPolicyFactory.h - build a RAT-selection policy from its string name.
//
#ifndef MULTIRATVANET_RATPOLICYFACTORY_H
#define MULTIRATVANET_RATPOLICYFACTORY_H

#include <memory>
#include <string>
#include "policies/IRatSelectionPolicy.h"

namespace multiratvanet {

class RatPolicyFactory {
  public:
    // Recognized names: "CoveragePriority", "Sinr", "LatencyQos", "Load", "Ml", "Ensemble", and
    // "ExampleSplit" (a template that puts each traffic class on its own RAT), and the one-RAT
    // baselines "OnlyDsrc", "OnlyWifi", "OnlyNr".
    // Returns nullptr for any other name.
    static std::unique_ptr<IRatSelectionPolicy> create(const std::string &name, const PolicyParams &params = PolicyParams());
};

} // namespace multiratvanet

#endif
