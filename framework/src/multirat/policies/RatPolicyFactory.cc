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
#include "policies/ExampleSplitPolicy.h"
#include "policies/SingleRatPolicy.h"

namespace multiratvanet {

std::unique_ptr<IRatSelectionPolicy> RatPolicyFactory::create(const std::string &name, const PolicyParams &p) {
    typedef std::unique_ptr<IRatSelectionPolicy> Ptr;
    if (name == "CoveragePriority")
        return Ptr(new CoveragePriorityPolicy(CoveragePriorityPolicy::defaultOrder(), p.timeToTrigger));
    if (name == "Sinr")
        return Ptr(new SinrPolicy(p.sinrMarginDb, p.timeToTrigger));
    if (name == "LatencyQos")
        return Ptr(new LatencyQosPolicy(p.maxLatencyMs, p.timeToTrigger));
    if (name == "Load")
        return Ptr(new LoadPolicy(p.loadMargin, p.timeToTrigger));
    if (name == "Ml")
        return Ptr(new MlPolicy(p.timeToTrigger));
    if (name == "Ensemble")
        return Ptr(new EnsemblePolicy(1.0, p));
    if (name == "ExampleSplit")
        return Ptr(new ExampleSplitPolicy(p.timeToTrigger));
    // baselines: one RAT only (the test bench compares the policies against these)
    if (name == "OnlyDsrc")
        return Ptr(new SingleRatPolicy(RatId::DSRC, "OnlyDsrc"));
    if (name == "OnlyWifi")
        return Ptr(new SingleRatPolicy(RatId::WIFI, "OnlyWifi"));
    if (name == "OnlyNr")
        return Ptr(new SingleRatPolicy(RatId::NR, "OnlyNr"));
    return nullptr;
}

} // namespace multiratvanet
