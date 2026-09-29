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
    // Recognized names: "CoveragePriority", "Sinr", "LatencyQos", "Load", "Ml".
    // Unknown names fall back to CoveragePriority.
    static std::unique_ptr<IRatSelectionPolicy> create(const std::string &name);
};

} // namespace multiratvanet

#endif
