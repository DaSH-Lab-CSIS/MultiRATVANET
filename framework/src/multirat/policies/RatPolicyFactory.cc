//
// RatPolicyFactory.cc
//
#include "policies/RatPolicyFactory.h"
#include "policies/CoveragePriorityPolicy.h"
#include "policies/SinrPolicy.h"
#include "policies/LatencyQosPolicy.h"
#include "policies/LoadPolicy.h"
#include "policies/MlPolicy.h"
#include "policies/EnsemblePolicy.h"

namespace multiratvanet {

std::unique_ptr<IRatSelectionPolicy> RatPolicyFactory::create(const std::string &name) {
    if (name == "Sinr")
        return std::unique_ptr<IRatSelectionPolicy>(new SinrPolicy());
    if (name == "LatencyQos")
        return std::unique_ptr<IRatSelectionPolicy>(new LatencyQosPolicy());
    if (name == "Load")
        return std::unique_ptr<IRatSelectionPolicy>(new LoadPolicy());
    if (name == "Ml")
        return std::unique_ptr<IRatSelectionPolicy>(new MlPolicy());
    if (name == "Ensemble")
        return std::unique_ptr<IRatSelectionPolicy>(new EnsemblePolicy());
    // default / "CoveragePriority"
    return std::unique_ptr<IRatSelectionPolicy>(new CoveragePriorityPolicy());
}

} // namespace multiratvanet
